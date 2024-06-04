from django import forms

from .fields import FacetField


class FacetForm(forms.Form):
    """
    A form for handling Elasticsearch facets.

    This form is used to collect and manage facet fields, making it easier to interact with Elasticsearch.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the FacetForm.

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
