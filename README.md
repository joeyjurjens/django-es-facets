# django-es-kit

**django-es-kit** is a robust toolkit designed to streamline your interaction with Elasticsearch within your Django application. Leveraging the power of [python-elasticsearch-dsl](https://github.com/elastic/elasticsearch-dsl-py) and [django-elasticsearch-dsl](https://github.com/django-es/django-elasticsearch-dsl/), it simplifies Elasticsearch integration for Django applications.

## Features

- **Faceted Search:** Simplifies faceted search implementation in Elasticsearch with forms, form fields, and views.

## Installation
```bash
pip install django-es-kit
```

### Forms & fields
`django-es-kit` comes with a prebuilt base `FacetForm` and some prebuilt form fields that allow you to add facets and filter fields to your form, which can then later be used to query Elasticsearch.

In order to create your own `FacetForm`, you'll need to subclass it:

```python
from django_es_kit.forms import FacetForm

class CatalogueForm(FacetForm):
    pass
```

`django-es-kit` comes with the following fields: `TermsFacetField`, `RangeFacetField` and `FilterField`. The `TermsFacetField` and `RangeFacetField` fields are used for facet filtering, while the `FilterField` is used for query filtering (in ES).

The `TermsFacetField` and `RangeFacetField` are subclasses of `FacetField`, which can be seen as interface.
A subclass of `FacetField` must implement the following method:

```python
class FacetField(forms.MultipleChoiceField):
    ...
    def get_es_facet(self) -> Facet:
        raise NotImplementedError(
            "You need to implement the method get_es_facet in your subclass."
    )
```

It must return a Facet instance, this is a class from the `python-elasticsearch-dsl` package.

The implementation for `TermsFacetField` is the following:
```python
class TermsFacetField(FacetField)
    ...
    def get_es_facet(self):
        return TermsFacet(field=self.es_field)
```

and for `RangeFacetField`:
```python
class RangeFacetField(FacetField):
    ...
    def get_es_facet(self):
        ranges = [
            (key, (range_.get("from"), range_.get("to")))
            for key, range_ in self.ranges.items()
        ]
        return RangeFacet(field=self.es_field, ranges=ranges)
```

As you can see, the implementation is pretty straight forward and not too difficult. If you want to create your own facet field, you can do so by subclassing `FacetField` and implementing the `get_es_facet` method. The `FacetField` class has some other methods that are used for applying the facet search, so you might need to look at those too. You can take inspiration from the `RangeFacetField`.

To use the facet fields, you can simply do so like you would with regular form fields, expect that it requires you to specify the `es_field`, which is the field name inside the Elasticsearch mapping. Also the facet fields are **not** `required` by default, so if you want a facet field to be required you have to explicitly say so by passing `required=True`

An example usage of the facet fields would look like this:
```python
from django_es_kit.forms import FacetForm
from django_es_kit.fields import TermsFacetField, RangeFacetField, RangeOption

class CatalogueForm(FacetForm):
    size = TermsFacetField(es_field="attributes.size")
    num_available = RangeFacetField(
        es_field="num_available",
        ranges=[
            RangeOption(upper=49, label="Up to 50"),
            RangeOption(lower=50, upper=100, label="50 to 100"),
            RangeOption(lower=100, label="100 or more"),
        ]
    )
    # Alternatively, if you don't want to use RangeOption you can also pass a list of dicts:
    num_available = RangeFacetField(
        es_field="num_available",
        ranges=[
            {"upper": 49, "label": "Up to 50"},
            {"lower": 50, "upper": 100, "label": "50 to 100"},
            {"lower": 100, "label": "100 or more"},
        ]
    )
```

The `FilterField` class isn't an actual form field by itself, it's just a interface that a field must implement:
```python
class FilterField:
    def get_es_filter_query(self, cleaned_data) -> Q:
        raise NotImplementedError(
            "You need to implement the method get_es_filter_query in your subclass."
        )
```

It must return a Q type, which is actually a function from `python-elasticsearch-dsl`. `django-es-kit` has no default implementation for it, as it really depends on what kind of filter you want to do. So in order to add filter fields to your form, you have to subclass a field with `FilterField` and implement the `get_es_filter_query` method.

An example implementation looks like this:

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

This is a custom form field that allows users to input the min and max price, the form field will then later be processed and do a range filter query based on the users input.

### Facated Search
`python-elasticsearch-dsl` comes with an abstraction class named [FacetedSearch](https://elasticsearch-dsl.readthedocs.io/en/latest/faceted_search.html). It makes faceted search a lot easier. `django-es-kit` comes with a subclass named `DynamicFacetedSearch`, which as the name implies, adds some dynamic capabilities. If you want to know how the `FacetedSearch` works in depth, I'd suggest reading the docs.

In order to create a faceted search page, you must create your own faceted search class, but you **MUST** subclass `DynamicFacetedSearch` and not `FacetedSearch` from `python-elasticsearch-dsl`

Your own faceted search class will likely be very small and look like this:
```python
class CatalogueFacetedSearch(DynamicFacetedSearch):
    doc_types = [Product]
    default_filter_queries = [
        Q("term", is_public=True),
    ]
```

This class specifies which doc_types it should use for searching and adds a default filter, which is a feature from the `DynamicFacetedSearch` class and is not required.
The doc_types must be a a list of classes that subclasses the `Document` from `python-elasticsearch-dsl`, you can find more about it [here](https://elasticsearch-dsl.readthedocs.io/en/latest/persistence.html#document).

Once you've create your faceted search class, you can create your faceted search view. `django-es-kit` comes with a generic view `ESFacetedSearchView`.
This class requires you to set the `faceted_search_class` and `form_class` class properties. Where `faceted_search_class` a subclass of `DynamicFacetedSearch` and `form_class` is a subclass of `FacetForm`.

The view itself makes no opinions on rendering, but it does add two things to the context data which you can and should use in your templates: `es_form` and `es_response`.
The `es_form` is the `form_class` you defined, but is now populated with available facet choices from Elasticsearch. The `es_response` is the `Response` class from `python-elasticsearch-dsl` which contains the reponse data, which you can use within your template.

An example view will look something like this:
```python
class CatalogueView(ESFacetedSearchView):
    form_class = CatalogueForm
    faceted_search_class = CatalogueFacetedSearch
    template_name = "django_oscar_es/products.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())
```

If you make use of `django-elasticsearch-dsl` and you have documents that subclass the Document class they provide, eg;
```python
from django_elasticsearch_dsl import Document
```

Then you will likely want to add the django model results to your context data as well. As documented in [django-elasticsearch-dsl](https://django-elasticsearch-dsl.readthedocs.io/en/latest/quickstart.html#search) you can get the queryset like this
```python
s = CarDocument.search().filter("term", color="blue")[:30]
qs = s.to_queryset()
```

Also, if you want to allow users to apply search query, you can implement the `get_search_query(self)` method on your `ESFacetedSearchView` subclass. This value will then be added as search query. An example implementation for this method might look like this:
```python
class CatalogueView(ESFacetedSearchView):
    ...
    def get_search_query(self):
        return self.request.GET.get("search_query")
```

If you want to search only within specific fields, you can add the `fields` property on your `DynamicFacetedSearch` subclass like this:
```python
class CatalogueFacetedSearch(DynamicFacetedSearch):
    fields = ["title^3", "upc^5", "description"]
```
As you can see, you can also boost fields if you want by adding the `^` symbol followed by the boost value. This is all functionality that comes with the `FacetedSearch` class from `python-elasticsearch-dsl`.
