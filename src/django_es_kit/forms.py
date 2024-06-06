from django import forms

from .fields import FacetField, FilterField, SortField


class FacetedSearchForm(forms.Form):
    """
    A form for handling Elasticsearch operations.

    This form is used to collect and manage facet fields, making it easier to interact with Elasticsearch.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the FacetedSearchForm.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        # Always have it accessible, even if it's empty (easier to do stuff with ES).
        self.cleaned_data = {}

    def get_es_facets(self):
        """
        Retrieve all Elasticsearch facets from the form fields.

        This method collects all `FacetField` instances from the form and
        returns them as a dictionary of Elasticsearch facets. These facets
        are then passed to the `FacetedSearch` class from within the view.

        Returns:
            dict: A dictionary where the keys are Elasticsearch field names and the values are `Facet` objects.
        """
        form_facets = {}
        for field in self.fields.values():
            if isinstance(field, FacetField):
                form_facets[field.es_field] = field.get_es_facet()
        return form_facets

    def get_facet_fields(self):
        """
        Retrieve all facet fields from the form.

        Returns:
            list: A list of `FacetField` instances.
        """
        return [
            field for field in self.fields.values() if isinstance(field, FacetField)
        ]

    def get_filter_fields(self):
        """
        Retrieve all filter fields from the form.

        Returns:
            list: A list of `FilterField` instances.
        """
        return [
            field for field in self.fields.values() if isinstance(field, FilterField)
        ]

    def get_sort_fields(self):
        """
        Retrieve all sort fields from the form.

        Returns:
            list: A list of `SortField` instances.
        """
        return [field for field in self.fields.values() if isinstance(field, SortField)]

    def get_regular_fields(self):
        """
        Retrieve all regular fields from the form.

        Returns:
            list: A list of regular form fields.
        """
        return [
            field
            for field in self.fields.values()
            if not isinstance(field, (FacetField, FilterField, SortField))
        ]
