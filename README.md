# django-es-kit

[![Coverage Status](https://codecov.io/gh/joeyjurjens/django-es-kit/branch/master/graph/badge.svg)](https://codecov.io/gh/joeyjurjens/django-es-kit)

**django-es-kit** is a django package that allows you easily create faceted search user interfaces. It's built upon [python-elasticsearch-dsl](https://github.com/elastic/elasticsearch-dsl-py) and [django-elasticsearch-dsl](https://github.com/django-es/django-elasticsearch-dsl/).

This package was initially build for [django-oscar-es](https://github.com/joeyjurjens/django-oscar-es), which is an integration between [django-oscar](https://github.com/django-oscar/django-oscar) and Elasticsearch. While writing this package, I figured it could be handy to create a separate package so I can use it for other projects as well. So the `django-oscar-es` code can be a good reference on how to work with this package.

## Features

- **Faceted Search:** A generic view that allows you to easily create faceted search interfaces
- **Planned:**
    - A generic view for auto complete / suggestions from Elasticsearch, including with a lightweight Javascript lib.

## Installation

First, install the package, eg with pip;
```bash
pip install django-es-kit
```

Second, since it depends on [django-elasticsearch-dsl](https://github.com/django-es/django-elasticsearch-dsl/), you'll also need to appropiate django settings. As of writing this, the only required setting that need to be set is:
```python
ELASTICSEARCH_DSL={
    'default': {
        'hosts': 'localhost:9200',
        'http_auth': ('username', 'password')
    }
}
```
Read the docs from [django-elasticsearch-dsl](https://django-elasticsearch-dsl.readthedocs.io/en/latest/settings.html) for all other settings it provides.

## Usage

### Faceted Search

In order to create a faceted search user interface, you'll need a few things:

- A `DynamicFacetedSearch` subclass with your own settings
- A `FacetForm` with `FacetField` and/or `FilterField`
- A `ESFacetedSearchView` subclass with your created `FacetForm` and `DynamicFacetedSearch` subclasses.

#### DynamicFacetedSearch

`python-elasticsearch-dsl` comes with an abstraction class named [FacetedSearch](https://elasticsearch-dsl.readthedocs.io/en/latest/faceted_search.html). This class makes faceted search a lot easier, as you don't have to manually handle the aggregation logic. However, the implementation is very static and assumes that most (if not all) decisions are made when you initialize the class.

That's where `DynamicFacetedSearch` comes in, it's a subclass of `FacetedSearch` which adds some dynamic capabilities. The usage of `DynamicFacetedSearch` does not differ much from `FacetedSearch`, so if you want to know how this class works in depth I'd suggest reading the docs linked above.

To create your own `FacetedSearch` class, you'd something like this:

```python
class CatalogueFacetedSearch(DynamicFacetedSearch):
    doc_types = [Product]
    default_filter_queries = [
        Q("term", is_public=True),
    ]
```

As you can see, the implementation is quite straight forward, you define the doc_type(s) and in this case I also added a default filter, which is a feature from the `DynamicFacetedSearch`.

#### FacetForm

The FacetForm is a very simple subclass of Django's default Form class. It has a method `get_es_facets` that returns all `FacetField` on the form, which is then later used within the `ESFacetedSearchView`

#### FacetField, TermsFacetField, RangeFacetField & FilterField

In order to allow users to apply filters, you have to add 'special' fields to your `FacetForm`.

There are two types of fields:

- `FacetField`
- `FilterField`

The `FacetField` is, as the name applies, for facets. It's a base class that fields should subclass while implementing the `get_es_facet` method:
```python
class FacetField(forms.MultipleChoiceField):
    ...
    def get_es_facet(self) -> Facet:
        raise NotImplementedError(
            "You need to implement the method get_es_facet in your subclass."
    )
```

This method must return a `Facet` instance, which is from the `python-elasticsearch-dsl` package.

`django-es-kit` comes with two prebuilt `FacetField` implementations:

- `TermsFacetField`
- `RangeFacetField`

Those fields are just regular form fields you are used to from Django, except that it has some extra required arguments when adding it to your form. It has the following extra arguments:

- `es_field` (**required**)
    - This is the field name in elasticsearch you wish users to be able to do filtering on.
- `field_type` (**required**)
    - This is the type within Elasticsearch for said field, this is required as we get the values as strings when users filter on them (GET params)
- `formatter` (**optional**)
    - This allows you to format the label being rendered for the available facet options.

And the `RangeFacetField` also has a `ranges` argument which is **required**. The ranges are a list of `RangeOption` or `dict`.

An example form with facet fields would look something like this:

```python
from django_es_kit.forms import FacetForm
from django_es_kit.fields import TermsFacetField, RangeFacetField, RangeOption

class CatalogueForm(FacetForm):
    size = TermsFacetField(es_field="attributes.size", field_type=str)
    num_available = RangeFacetField(
        es_field="num_available",
        field_type=int,
        ranges=[
            RangeOption(upper=49, label="Up to 50"),
            RangeOption(lower=50, upper=100, label="50 to 100"),
            RangeOption(lower=100, label="100 or more"),
        ]
    )
    # Alternatively, if you don't want to use RangeOption you can also pass a list of dicts:
    num_available = RangeFacetField(
        es_field="num_available",
        field_type=int,
        ranges=[
            {"upper": 49, "label": "Up to 50"},
            {"lower": 50, "upper": 100, "label": "50 to 100"},
            {"lower": 100, "label": "100 or more"},
        ]
    )
```

And then we have the `FilterField`, this is base class for creating form fields for 'regular' filtering within Elasticsearch. It requires you to implement the `get_es_filter_query` method:
```python
class FilterField:
    def get_es_filter_query(self, cleaned_data) -> Q:
        raise NotImplementedError(
            "You need to implement the method get_es_filter_query in your subclass."
        )
```

It must return a Q type, which is actually a function from `python-elasticsearch-dsl`.

Unlike the `FacetField`, there's no default implementation for `FilterField` as it's up to you how and what the user should be able to filter on. However, in the `django-oscar-es` package I have created the `PriceInputFilterField`, which allows users to enter the minimum and maximum price. That implementation looks like this:

```python
class PriceInputWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [
            forms.NumberInput(attrs={"placeholder": _("Min price")}),
            forms.NumberInput(attrs={"placeholder": _("Max price")}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value[0], value[1]]
        return [None, None]


class PriceInputField(forms.MultiValueField, FilterFormField):
    widget = PriceInputWidget

    def __init__(self, *args, **kwargs):
        fields = [
            forms.DecimalField(required=False),
            forms.DecimalField(required=False),
        ]
        super().__init__(fields, *args, **kwargs)

    def compress(self, data_list):
        return data_list

    def get_es_filter_query(self, cleaned_data):
        if cleaned_data:
            return Q("range", price={"gt": cleaned_data[0], "lt": cleaned_data[1]})
        return None
```

#### ESFacetedSearchView

The `ESFacetedSearchView` is a generic view you can use to create a view for faceted search. In order to use this view, you must set the `form_class` and `faceted_search_class` attributes.

```python
class CatalogueView(ESFacetedSearchView):
    form_class = CatalogueForm
    faceted_search_class = CatalogueFacetedSearch
```

`ESFacetedSearchView` subclasses Django's `View` class, so it does not implement any rendering, this is up to you. What it does do, is add `es_form` and `es_response` to the context. The `es_form` facet fields are now populated with avaialable choices that Elasticsearch returned based on the request.

Sometimes you might allow users to also do a search query through a input field. This is also supported, but you must implement the `get_search_query` method to return the value of the query param that should be used for this.
```python
class CatalogueView(ESFacetedSearchView):
    ...
    def get_search_query(self):
        return self.request.GET.get("search_query")
```

If you want to only search within specific fields, you can set that on your `FacetedSearch` class:
```python
class CatalogueFacetedSearch(DynamicFacetedSearch):
    fields = ["title^3", "upc^5", "description"]
```
As you can see, you can also boost fields if you want by adding the `^` symbol followed by the boost value.
