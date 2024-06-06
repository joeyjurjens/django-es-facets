from django.core.paginator import Paginator
from django.utils.functional import cached_property


class ESPaginator(Paginator):
    # pylint: disable=too-many-arguments
    def __init__(
        self, es_response, object_list, per_page, orphans=0, allow_empty_first_page=True
    ):
        self.es_response = es_response
        super().__init__(object_list, per_page, orphans, allow_empty_first_page)

    @cached_property
    def count(self):
        count = self.es_response.hits.total.value
        return count
