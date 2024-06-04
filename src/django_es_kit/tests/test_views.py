import pytest

from testcontainers.elasticsearch import ElasticSearchContainer

from elasticsearch_dsl.connections import connections

from django_elasticsearch_dsl.documents import Document
from django_elasticsearch_dsl.registries import registry
from django_elasticsearch_dsl import fields

from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from ..views import ESFacetedSearchView
from ..forms import FacetForm
from ..fields import TermsFacetField
from ..faceted_search import DynamicFacetedSearch


@pytest.fixture(scope="class")
def elasticsearch_container():
    container = ElasticSearchContainer("elasticsearch:8.13.4", mem_limit="3G")
    container.start()
    # Set python-elasticsearch-dsl host to the container
    connections.configure(default={"hosts": container.get_url()})
    yield container
    container.stop()


@registry.register_document
class UserDocument(Document):
    class Index:
        name = "users"

    class Django:
        model = User
        fields = [
            "is_staff",
            "is_active",
            "is_superuser",
        ]

    username = fields.TextField(
        attr="username", fields={"keyword": fields.KeywordField()}
    )
    first_name = fields.TextField(
        attr="first_name", fields={"keyword": fields.KeywordField()}
    )
    last_name = fields.TextField(
        attr="last_name", fields={"keyword": fields.KeywordField()}
    )
    email = fields.TextField(attr="email", fields={"keyword": fields.KeywordField()})


# pylint: disable=unused-argument
def is_role_formatter(request, key, doc_count):
    if key is True:
        return f"Yes ({doc_count})"
    return f"No ({doc_count})"


class UsersFacetForm(FacetForm):
    username = TermsFacetField(es_field="username.keyword", field_type=str)
    first_name = TermsFacetField(es_field="first_name.keyword", field_type=str)
    last_name = TermsFacetField(es_field="last_name.keyword", field_type=str)
    email = TermsFacetField(es_field="email.keyword", field_type=str)
    is_staff = TermsFacetField(
        es_field="is_staff", field_type=bool, formatter=is_role_formatter
    )
    is_active = TermsFacetField(
        es_field="is_active", field_type=bool, formatter=is_role_formatter
    )
    is_superuser = TermsFacetField(
        es_field="is_superuser", field_type=bool, formatter=is_role_formatter
    )


class UsersFacetetedSearch(DynamicFacetedSearch):
    doc_types = [UserDocument]


class UsersFacetedSearchView(ESFacetedSearchView):
    faceted_search_class = UsersFacetetedSearch
    form_class = UsersFacetForm


@pytest.mark.usefixtures("elasticsearch_container")
# pylint: disable=attribute-defined-outside-init
class TestESFacetedSearchView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = UsersFacetedSearchView()
        self.setup_index()

    def setup_index(self):
        users_data = [
            {
                "username": "john_doe",
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_staff": True,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "jane_smith",
                "email": "jane.smith@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "is_staff": False,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "alice_johnson",
                "email": "alice.johnson@example.com",
                "first_name": "Alice",
                "last_name": "Johnson",
                "is_staff": True,
                "is_active": False,
                "is_superuser": True,
            },
            {
                "username": "bob_brown",
                "email": "bob.brown@example.com",
                "first_name": "Bob",
                "last_name": "Brown",
                "is_staff": True,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "emma_williams",
                "email": "emma.williams@example.com",
                "first_name": "Emma",
                "last_name": "Williams",
                "is_staff": False,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "william_jones",
                "email": "william.jones@example.com",
                "first_name": "William",
                "last_name": "Jones",
                "is_staff": True,
                "is_active": False,
                "is_superuser": True,
            },
            {
                "username": "olivia_davis",
                "email": "olivia.davis@example.com",
                "first_name": "Olivia",
                "last_name": "Davis",
                "is_staff": True,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "liam_taylor",
                "email": "liam.taylor@example.com",
                "first_name": "Liam",
                "last_name": "Taylor",
                "is_staff": False,
                "is_active": True,
                "is_superuser": False,
            },
            {
                "username": "ava_wilson",
                "email": "ava.wilson@example.com",
                "first_name": "Ava",
                "last_name": "Wilson",
                "is_staff": True,
                "is_active": False,
                "is_superuser": True,
            },
            {
                "username": "noah_evans",
                "email": "noah.evans@example.com",
                "first_name": "Noah",
                "last_name": "Evans",
                "is_staff": True,
                "is_active": True,
                "is_superuser": False,
            },
        ]
        for user_data in users_data:
            User.objects.create(**user_data)

        call_command("search_index", "--rebuild", "-f")

    def test_get_context_data(self):
        request = self.factory.get("/")
        self.view.setup(request)
        context = self.view.get_context_data()
        assert "es_form" in context
        assert "es_response" in context

        # Make sure the formatter that is set to the role fields works
        role_fields = ["is_staff", "is_active", "is_superuser"]
        for role_field in role_fields:
            form_field = context["es_form"].fields[role_field]
            for choice in form_field.choices:
                value, label = choice
                assert value in [True, False]
                assert "Yes" in label or "No" in label

    def test_no_filters_get_es_response(self):
        request = self.factory.get("/")
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert response["hits"]["total"]["value"] == User.objects.count()

    def test_facet_username(self):
        request = self.factory.get("/", {"username": "john_doe"})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(username="john_doe").count()
        )

    def test_facet_first_name(self):
        request = self.factory.get("/", {"first_name": "John"})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(first_name="John").count()
        )

    def test_facet_last_name(self):
        request = self.factory.get("/", {"last_name": "Doe"})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(last_name="Doe").count()
        )

    def test_facet_email(self):
        request = self.factory.get("/", {"email": "john.doe@example.com"})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(email="john.doe@example.com").count()
        )

    def test_facet_is_staff(self):
        request = self.factory.get("/", {"is_staff": True})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(is_staff=True).count()
        )

    def test_facet_is_active(self):
        request = self.factory.get("/", {"is_active": True})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(is_active=True).count()
        )

    def test_facet_is_superuser(self):
        request = self.factory.get("/?", {"is_superuser": True})
        self.view.request = request
        response = self.view.get_es_response()
        assert "hits" in response
        assert (
            response["hits"]["total"]["value"]
            == User.objects.filter(is_superuser=True).count()
        )
