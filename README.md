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
- A `FacetedSearchForm` with `FacetField` and/or `FilterField`
- A `ESFacetedSearchView` subclass with your created `FacetedSearchForm` and `DynamicFacetedSearch` subclasses.

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

#### FacetedSearchForm

The FacetedSearchForm is a very simple subclass of Django's default Form class. It has a method `get_es_facets` that returns a dictionary of facets which can be passed to the `DynamicFacetedSearch` class. It also has some helper methods that you can use to render your form: `get_facet_fields` `get_filter_fields` `get_sort_fields` & `get_regular_fields`, the names speaks for themselves. Those methods could be useful, as most likely you'll render those types of fields in groups.

#### FacetField, TermsFacetField, RangeFacetField, FilterField & SortField

In order to allow users to apply filters, you have to add 'special' fields to your `FacetedSearchForm`.

There are three types of fields:

- `FacetField`
- `FilterField`
- `SortField`

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

Those fields are just regular form fields you are used to from Django, except that it has some extra arguments when adding it to your form. It has the following extra arguments:

- `es_field` (**required**)
    - This is the field name in elasticsearch you wish users to be able to do filtering on.
- `field_type` (**required**)
    - This is the type within Elasticsearch for said field, this is required as we get the values as strings when users filter on them (GET params)
- `formatter` (**optional**)
    - This allows you to format the label being rendered for the available facet options.
- `size` (**optional**)
    - This allows you to specify the amount of facets to return (defaults to 10)

And the `RangeFacetField` also has a `ranges` argument which is **required**. The ranges are a list of `RangeOption` or `dict`.

An example form with facet fields would look something like this:

```python
from django_es_kit.forms import FacetedSearchForm
from django_es_kit.fields import TermsFacetField, RangeFacetField, RangeOption

def num_stock_formatter(request, key, doc_count):
    return f"{key} pieces ({doc_count})"

class CatalogueForm(FacetedSearchForm):
    size = TermsFacetField(es_field="attributes.size", field_type=str)
    num_available = RangeFacetField(
        es_field="num_available",
        field_type=int,
        formatter=num_stock_formatter,
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

Unlike the `FacetField`, there's no default implementation for `FilterField` as it's up to you how and what the user should be able to filter on. However, in the `django-oscar-es` package, There's the `PriceInputFilterField`, which allows users to enter the minimum and maximum price. That implementation looks like this:

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

The `SortField` allows the users to sort the results. This field is quite straight forward, as it only requires you to set `sort_choices`. The `sort_choices` are a list of tuples containing three items: `key/value`, `label`, `elasticsearch sort`. So the only difference compared to the default `ChoiceField` from Django, is that the tuple now requires a third item to specifiy what Elasticsearch field and which direction to sort on.
```python
class ProductFacetedSearchForm(FacetedSearchForm):
    RELEVANCY = "relevancy"
    TOP_RATED = "rating"
    NEWEST = "newest"
    PRICE_HIGH_TO_LOW = "price-desc"
    PRICE_LOW_TO_HIGH = "price-asc"
    TITLE_A_TO_Z = "title-asc"
    TITLE_Z_TO_A = "title-desc"

    SORT_BY_CHOICES = [
        (RELEVANCY, _("Relevancy"), "_score"),
        (TOP_RATED, _("Customer rating"), "-rating"),
        (NEWEST, _("Newest"), "-date_created"),
        (PRICE_HIGH_TO_LOW, _("Price high to low"), "-price"),
        (PRICE_LOW_TO_HIGH, _("Price low to high"), "price"),
        (TITLE_A_TO_Z, _("Title A to Z"), "title.keyword"),
        (TITLE_Z_TO_A, _("Title Z to A"), "-title.keyword"),
    ]

    sort_option = SortField(SORT_BY_CHOICES, required=False)
```

The third item in the tuple is the same format `python-elasticsearch-dsl` uses, so you can also do things like this:
```python
CHOICES = [
    ("lines", "Order lines", {"lines" : {"order" : "asc", "mode" : "avg"}})
]
```

You can read more about it [here](https://elasticsearch-dsl.readthedocs.io/en/latest/search_dsl.html#sorting).

#### ESFacetedSearchView & ESFacetedSearchListView

The `ESFacetedSearchView` and `ESFacetedSearchListView` are generic views you can use to create a views for faceted search. In order to use those views, you must set the `form_class` and `faceted_search_class` attributes.

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

Then we have the `ESFacetedSearchListView`, which is a subclass of `ESFacetedSearchView` and Django's `ListView`. It allows you to easily create a list view based on the elasticsearch response. The response is converted to a queryset (this is a feature from `django-elasticsearch-dsl`) and it has a custom paginator to make use of the elasticsearch response for some parts.

In order to use `ESFacetedSearchListView`, you have to meet the following requirements:

- Your `faceted_search_class` must have only one Document in the doc_types list.
- The Document inside the doc_types list must be a subclass of `django-elasticsearch-dsl` Document, as it requires you to set a Django model which is needed to be able to call the `to_queryset` method.
