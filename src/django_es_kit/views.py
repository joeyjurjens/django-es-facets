import logging

from django.views.generic import View, ListView
from django.views.generic.base import ContextMixin

from .faceted_search import DynamicFacetedSearch
from .forms import FacetedSearchForm
from .fields import FacetField, FilterField, SortField
from .paginator import ESPaginator

logger = logging.getLogger(__name__)


class ESFacetedSearchView(ContextMixin, View):
    """
    A view for handling faceted search with Elasticsearch.

    This view integrates with Elasticsearch to perform faceted searches and handle form data
    for filtering search results.

    Attributes:
        faceted_search_class (type): The class used for faceted search, must be a subclass of `DynamicFacetedSearch`.
        form_class (type): The form class used for filtering, must be a subclass of `FacetedSearchForm`.
    """

    faceted_search_class = None
    form_class = None

    def __init__(self, *args, **kwargs):
        """
        Initialize the ESFacetedSearchView.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Raises:
            NotImplementedError: If `faceted_search_class` or `form_class` is not defined.
            ValueError: If `faceted_search_class` is not a subclass of `DynamicFacetedSearch` or
                        if `form_class` is not a subclass of `FacetedSearchForm`.
        """
        if not self.get_faceted_search_class():
            raise NotImplementedError("The class must have a faceted_search_class")

        if not issubclass(self.get_faceted_search_class(), DynamicFacetedSearch):
            raise ValueError(
                "The faceted_search_class must be a subclass of DynamicFacetedSearch"
            )

        if not self.get_form_class():
            raise NotImplementedError("The class must have a form_class")

        if not issubclass(self.get_form_class(), FacetedSearchForm):
            raise ValueError("The form_class must be a subclass of FacetedSearchForm")

        self._faceted_search = None
        self._form = None
        self._es_response = None
        super().__init__(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Get the context data for the view.

        Args:
            **kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The context data with the form and Elasticsearch response.
        """
        ctx = super().get_context_data(**kwargs)
        ctx["es_form"] = self.get_form()
        ctx["es_response"] = self.get_es_response()
        return ctx

    def get_search_query(self):
        """
        Get the search query.

        This method can be overridden to provide a custom search query.

        Returns:
            None: The default implementation returns None.
        """
        return None

    def get_faceted_search_class(self):
        """
        Get the faceted search class.

        Returns:
            type: The faceted search class.
        """
        return self.faceted_search_class

    def get_faceted_search(self):
        """
        Get the faceted search instance.

        Returns:
            DynamicFacetedSearch: The faceted search instance.
        """
        if self._faceted_search:
            return self._faceted_search

        faceted_search_class = self.get_faceted_search_class()
        # pylint: disable=not-callable
        self._faceted_search = faceted_search_class(
            facets=self.get_form().get_es_facets(), query=self.get_search_query()
        )
        return self._faceted_search

    def get_form_class(self):
        """
        Get the form class.

        Returns:
            type: The form class.
        """
        return self.form_class

    def get_form(self):
        """
        Get the form instance.

        Returns:
            FacetedSearchForm: The form instance.
        """
        if self._form:
            return self._form

        form_class = self.get_form_class()
        if self.request.GET:
            # pylint: disable=not-callable
            self._form = form_class(self.request.GET)
            return self._form

        # pylint: disable=not-callable
        self._form = form_class()
        return self._form

    def get_es_response(self):
        """
        Get the Elasticsearch response.

        Returns:
            FacetedResponse: The Elasticsearch response.
        """
        if self._es_response:
            return self._es_response

        faceted_search = self.get_faceted_search()
        form = self.get_form()

        if self.request.GET:
            form.is_valid()

        if not form.cleaned_data:
            self._es_response = self.execute_search(faceted_search)
            self.reflect_es_response_to_form_fields(self._es_response, form)
            return self._es_response

        self.apply_filters(form, faceted_search)
        self._es_response = self.execute_search(faceted_search)
        self.reflect_es_response_to_form_fields(self._es_response, form)
        return self._es_response

    def execute_search(self, faceted_search):
        """
        Execute the faceted search.

        Args:
            faceted_search (DynamicFacetedSearch): The faceted search instance.

        Returns:
            FacetedResponse: The search results.
        """
        return faceted_search.execute()

    def apply_filters(self, form, faceted_search):
        """
        Apply filters from the form to the faceted search.

        Args:
            form (FacetedSearchForm): The form instance.
            faceted_search (DynamicFacetedSearch): The faceted search instance.
        """
        for key, value in form.cleaned_data.items():
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
            elif isinstance(form_field, SortField):
                sort_field = form_field.sort_mapping.get(value)
                if sort_field:
                    faceted_search.add_sort(sort_field)

    def reflect_es_response_to_form_fields(self, es_response, form):
        """
        Add all available facet choices from the response to the form fields.

        Args:
            es_response (FacetedResponse): The Elasticsearch response.
            form (FacetedSearchForm): The form instance.
        """
        if not hasattr(es_response, "facets"):
            return

        for field in form.fields.values():
            if isinstance(field, FacetField) and field.es_field in es_response.facets:
                field.process_facet_buckets(
                    self.request, es_response.facets[field.es_field]
                )


# pylint: disable=too-many-ancestors
class ESFacetedSearchListView(ListView, ESFacetedSearchView):
    paginator_class = ESPaginator

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        doc_types = self.get_faceted_search_class().doc_types
        if not doc_types or len(doc_types) > 1:
            raise ValueError(
                "In order to use the ESFacetedSearchListView, the search_class must have exactly one doc_type."
            )

    def get_paginator(
        self, queryset, per_page, orphans=0, allow_empty_first_page=True, **kwargs
    ):
        """
        Pass the elasticsearch response to the paginator.
        """
        return self.paginator_class(
            self.get_es_response(),
            queryset,
            per_page,
            orphans=orphans,
            allow_empty_first_page=allow_empty_first_page,
            **kwargs,
        )

    def paginate_queryset(self, queryset, page_size):
        """
        This method is overidden to return the orignal passed queryset rather than the paginated queryset.
        This because we paginated the elasticsearch response, and this response is used to create the queryset
        and thus we don't have to paginate the queryset anymore.
        """
        paginator, page, _, is_paginated = super().paginate_queryset(
            queryset, page_size
        )
        return paginator, page, queryset, is_paginated

    def get_queryset(self):
        es_response = self.get_es_response()
        # pylint: disable=protected-access
        qs = es_response._search.to_queryset()
        return qs

    def get_faceted_search(self):
        faceted_search = super().get_faceted_search()
        page = (
            self.kwargs.get(self.page_kwarg)
            or self.request.GET.get(self.page_kwarg)
            or 1
        )
        faceted_search.set_pagination(page=int(page), page_size=self.paginate_by)
        return faceted_search
