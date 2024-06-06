import logging

from elasticsearch_dsl import FacetedSearch, FacetedResponse
from elasticsearch_dsl.query import Query

from django_elasticsearch_dsl.search import Search

logger = logging.getLogger(__name__)


class DynamicFacetedSearch(FacetedSearch):
    """
    This class adds some extra functionality compared to the base class FacetedSearch:

    1. Dynamic facet fields, by default you must define them on the Meta class, but with this
       class you can add them dynamically. This allows us to add facets from django forms which
       can also in return be populated from the database.
    2. Allow defining default query filters on the class (`default_filter_queries`)
    3. Allow dynamically adding extra query filters (`add_filter_query`)
    4. Allow pagination on the search results (`set_pagination`)

    Attributes:
        doc_types (list): List of document types for the search.
        default_filter_queries (list): List of default filter queries.
    """

    doc_types = []
    default_filter_queries = []

    def __init__(self, facets, query=None, filters=None, sort=()):
        """
        Initialize the DynamicFacetedSearch with dynamic facets and pagination.

        Args:
            facets (dict): Facet fields.
            query (str, optional): Query string.
            filters (dict, optional): Dictionary of filters. Defaults to None.
            sort (tuple, optional): Tuplce of sort fields. Defaults to ().
        """
        if filters is None:
            filters = {}
        self.facets = facets
        self.filter_queries = []
        self.page = None
        self.page_size = None
        super().__init__(query=query, filters=filters, sort=sort)

    def _validate_pagination(self, page, page_size):
        """
        Validate pagination parameters.

        Args:
            page (int): Page number.
            page_size (int): Number of results per page.

        Raises:
            ValueError: If `page` or `page_size` are not positive integers.
        """
        if not isinstance(page, int) or not isinstance(page_size, int):
            raise ValueError("page and page_size must be integers")
        if page < 1:
            raise ValueError("page must be greater than 0")
        if page_size < 1:
            raise ValueError("page_size must be greater than 0")

    def add_filter_query(self, filter_query):
        """
        Add a filter query to the search.

        Args:
            filter_query (Query): A filter query to be added.

        Raises:
            ValueError: If `filter_query` is not an instance of `elasticsearch_dsl.Query`.
        """
        if not isinstance(filter_query, Query):
            logger.error(
                "filter_query must be an instance of elasticsearch_dsl.Query, the filter_query: '%s' has not been added",
                filter_query,
            )
            return
        self.filter_queries.append(filter_query)

    def add_sort(self, sort):
        """
        Add a sort field to the search.

        Args:
            sort (str): The sort field.
        """
        if isinstance(self._sort, tuple):
            self._sort = list(self._sort)
        self._sort.append(sort)

    def set_pagination(self, page, page_size):
        """
        Set pagination parameters.

        Args:
            page (int): Page number.
            page_size (int): Number of results per page.

        Raises:
            ValueError: If `page` or `page_size` are not positive integers.
        """
        self._validate_pagination(page, page_size)
        self.page = page
        self.page_size = page_size

    def query(self, search, query):
        """
        Apply the query to the search object.

        Args:
            search (Search): The search object.
            query (str): The query string.

        Returns:
            Search: The updated search object with the query, default filters and filter queries applied.
        """
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
        Create a search object using the django-elasticsearch-dsl Search class.

        Note:
            It'll include the model if there is only one doc_type, otherwise it'll be None.
            If you have multiple doc_types, you can't use the to_queryset method later on.

        Returns:
            Search: The search object.
        """
        if len(self.doc_types) > 1:
            model = None
            logger.warning(
                "Your FacetedSearch class has no or multiple doc_types, this means you can NOT use the to_queryset method"
            )
        else:
            model = self.doc_types[0].Django.model

        s = Search(
            model=model, doc_type=self.doc_types, index=self.index, using=self.using
        )
        return s.response_class(FacetedResponse)

    def paginate(self, search):
        """
        Paginate the search results.

        Args:
            search (Search): The search object.

        Returns:
            Search: The paginated search object.
        """
        return search[(self.page - 1) * self.page_size : self.page * self.page_size]

    def build_search(self):
        """
        Build the search object with pagination.

        Returns:
            Search: The search object with pagination applied.
        """
        s = super().build_search()
        if self.page and self.page_size:
            s = self.paginate(s)
        return s

    def execute(self):
        """
        Execute the search query.

        Rebuild the search object to apply dynamic filters before executing the search.

        Returns:
            Response: The search response.
        """
        self._s = self.build_search()
        return super().execute()
