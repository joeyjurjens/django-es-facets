import logging

from elasticsearch_dsl import FacetedSearch, Q, FacetedResponse
from elasticsearch_dsl.query import Query
from django_elasticsearch_dsl.search import Search

logger = logging.getLogger(__name__)


class DynamicFacetedSearch(FacetedSearch):
    """
    This class adds some extra functionality compared to the base class FacetedSearch:
    1. Dynamic facet fields, by default you must define them on the Meta class, but with this
    class you can add them dynamically. This allows us to add facets from django forms which
    can also in return be populated from the database.
    2. Allow defining default query filters on the class (default_filter_queries)
    3. Allow dynamically adding extra query filters (add_filter_query)
    4. Allow pagination on the search results (set_pagination or  page & page_size arguments)
    """

    default_filter_queries = []

    def __init__(self, facets, query=None, filters={}, sort=(), page=1, page_size=10):
        self.facets = facets
        self.filter_queries = []
        self._validate_pagination(page, page_size)
        self.page = page
        self.page_size = page_size
        super().__init__(query=query, filters=filters, sort=sort)

    def _validate_pagination(self, page, page_size):
        if not isinstance(page, int) or not isinstance(page_size, int):
            raise ValueError("page and page_size must be integers")

        if page < 1:
            raise ValueError("page must be greater than 0")

        if page_size < 1:
            raise ValueError("page_size must be greater than 0")

    def add_filter_query(self, filter_query):
        if not isinstance(filter_query, Query):
            logger.error(
                "filter_query must be an instance of elasticsearch_dsl.Query, the filter_query: '%s' has not been added",
                filter_query,
            )
            return
        self.filter_queries.append(filter_query)

    def set_pagination(self, page, page_size):
        self._validate_pagination(page, page_size)
        self.page = page
        self.page_size = page_size

    def query(self, search, query):
        search = super().query(search, query)

        # Apply all default filter queries
        for filter_query in self.default_filter_queries:
            if not isinstance(filter_query, Query):
                logger.error(
                    "filter_query must be an instance of elasticsearch_dsl.Query, the filter_query '%s' has not been added",
                    filter_query,
                )
                continue
            search = search.filter(filter_query)

        # Apply all other dynamically added query filters
        for filter_query in self.filter_queries:
            search = search.filter(filter_query)

        return search

    def search(self):
        """
        Make sure to use the django-elasticsearch-dsl Search object, so you can call to_queryset on it.
        Note: This only works if you have ONE doc_type in your FacetedSearch class.
        """
        if len(self.doc_types) > 1:
            model = None
            logger.warning(
                "Your FacetedSearch class has multiple doc_types, this means you can NOT use the to_queryset method"
            )
        else:
            model = self.doc_types[0].Django.model

        s = Search(
            model=model, doc_type=self.doc_types, index=self.index, using=self.using
        )
        return s.response_class(FacetedResponse)

    def paginate(self, search):
        return search[(self.page - 1) * self.page_size : self.page * self.page_size]

    def build_search(self):
        s = super().build_search()
        s = self.paginate(s)
        return s

    def execute(self):
        """
        The original FacetedSearch builds the search object in the __init__ method.
        This is because they assume every filtering decision is made from the __init__ arguments.
        But we allow all sort of dynamic filtering, so we re-build the search object right before executing it.
        Eg in ESFacetedSearchView we call the add_filter method to apply form filters.
        """
        self._s = self.build_search()
        return super().execute()
