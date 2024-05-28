import logging

from elasticsearch_dsl import FacetedSearch, Q
from elasticsearch_dsl.query import Query

logger = logging.getLogger(__name__)


class DynamicFacetedSearch(FacetedSearch):
    """
    This class adds some extra functionality compared to the base class FacetedSearch:
    1. Dynamic facet fields, by default you must define them on the Meta class, but with this
    class you can add them dynamically. This allows us to add facets from django forms which
    can also in return be populated from the database.
    2. Allow defining default query filters on the class (default_filter_queries)
    3. Allow dynamically adding extra query filters (add_filter_query)
    """

    default_filter_queries = []

    def __init__(self, facets, query=None, filters={}, sort=()):
        self.facets = facets
        self.filter_queries = []
        super().__init__(query=query, filters=filters, sort=sort)

    def add_filter_query(self, filter_query):
        if not isinstance(filter_query, Query):
            logger.error(
                "filter_query must be an instance of elasticsearch_dsl.Query, the filter_query: '%s' has not been added",
                filter_query,
            )
            return
        self.filter_queries.append(filter_query)

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

    def execute(self):
        """
        The original FacetedSearch builds the search object in the __init__ method.
        This is because they assume every filtering decision is made from the __init__ arguments.
        But we allow all sort of dynamic filtering, so we re-build the search object right before executing it.
        Eg in ESFacetedSearchView we call the add_filter method to apply form filters.
        """
        self._s = self.build_search()
        return super().execute()
