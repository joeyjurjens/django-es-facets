import logging

from django.views.generic import View

from .faceted_search import DynamicFacetedSearch
from .forms import FacetForm
from .fields import FacetField, FilterField

logger = logging.getLogger(__name__)


class ESFacetedSearchView(View):
    faceted_search_class = None
    form_class = None

    def __init__(self, *args, **kwargs):
        if not self.get_faceted_search_class():
            raise NotImplementedError("The class must have a faceted_search_class")

        if not issubclass(self.get_faceted_search_class(), DynamicFacetedSearch):
            raise ValueError(
                "The faceted_search_class must be a subclass of DynamicFacetedSearch"
            )

        if not self.get_form_class():
            raise NotImplementedError("The class must have a form_class")

        if not issubclass(self.get_form_class(), FacetForm):
            raise ValueError("The form_class must be a subclass of FacetForm")

        self._faceted_search = None
        self._form = None
        super().__init__(*args, **kwargs)

    def get_search_query(self):
        return None

    def get_faceted_search_class(self):
        return self.faceted_search_class

    def get_faceted_search(self):
        if self._faceted_search:
            return self._faceted_search

        faceted_search_class = self.get_faceted_search_class()
        self._faceted_search = faceted_search_class(
            facets=self.get_form().get_es_facets(), query=self.get_search_query()
        )
        return self._faceted_search

    def get_form_class(self):
        return self.form_class

    def get_form(self):
        if self._form:
            return self._form

        form_class = self.get_form_class()
        if self.request.GET:
            self._form = form_class(self.request.GET)
            return self._form

        self._form = form_class()
        return self._form

    def get_es_response(self, form):
        faceted_search = self.get_faceted_search()
        form = self.get_form()

        # Trigger cleaned_data population
        if self.request.GET:
            form.is_valid()

        # No filters to apply
        if not form.cleaned_data:
            es_response = faceted_search.execute()
            self.reflect_es_response_to_form_fields(es_response, form)
            return es_response

        # Apply filters before executing the search based on the form data
        for key, value in form.cleaned_data.items():
            # Fuck off
            if key not in form.fields:
                continue

            form_field = form.fields[key]
            if isinstance(form_field, FacetField):
                try:
                    faceted_search.add_filter(
                        form_field.es_field, form_field.get_es_filter_value(value)
                    )
                except KeyError:
                    logger.warning(
                        "Could not apply filter for field %s. This is likely because of an invalid query parameter for this facet.",
                        form_field.es_field,
                    )
            elif isinstance(form_field, FilterField):
                es_filter_query = form_field.get_es_filter_query(value)
                if es_filter_query:
                    faceted_search.add_filter_query(es_filter_query)

        # Add this point we have added all filters, so we can perform the query to ES.
        es_response = faceted_search.execute()
        self.reflect_es_response_to_form_fields(es_response, form)
        return es_response

    def reflect_es_response_to_form_fields(self, es_response, form):
        """
        This method adds all available facet choices from the response to the facet form fields.
        """
        for field in form.fields.values():
            if isinstance(field, FacetField) and field.es_field in es_response.facets:
                field.process_facet_buckets(es_response.facets[field.es_field])

    def get_context_data(self, **kwargs):
        form = self.get_form()
        es_response = self.get_es_response(form)
        return {"es_form": form, "es_response": es_response}
