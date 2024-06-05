import logging

from elasticsearch_dsl import Q, Facet, TermsFacet, RangeFacet

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class FacetField(forms.MultipleChoiceField):
    """
    A form field for handling Elasticsearch facets as multiple choice fields.

    Attributes:
        es_field (str): The name of the field in the Elasticsearch index.
        field_type (type): The type of the field (e.g., int, str, bool).
        formatter (callable, optional): A function that formats the facet values.
    """

    widget = forms.CheckboxSelectMultiple

    def __init__(self, es_field, field_type, formatter=None, **kwargs):
        """
        Initialize the FacetField.

        Args:
            es_field (str): The field name in the Elasticsearch index.
            field_type (type): The type of the field (e.g., int, str, bool).
            formatter (callable, optional): A function that formats the facet values.
            **kwargs: Additional keyword arguments for the field.
        """
        self.es_field = es_field
        self.field_type = field_type
        self.formatter = formatter
        if "required" not in kwargs:
            kwargs["required"] = False
        super().__init__(**kwargs)

    def get_es_facet(self) -> Facet:
        """
        Get the Elasticsearch facet.

        Returns:
            Facet: The Elasticsearch facet.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        raise NotImplementedError(
            "You need to implement the method get_es_facet in your subclass."
        )

    def validate(self, value):
        """
        Validate the field value.

        Args:
            value (list): The value to validate.

        Raises:
            ValidationError: If the field is required but no value is provided.
        """
        if self.required and not value:
            raise ValidationError(self.error_messages["required"], code="required")

    def get_es_filter_value(self, raw_value):
        """
        Get the Elasticsearch filter value.

        Args:
            raw_value (list): The raw value from the form input.

        Returns:
            list: The filtered values converted to the correct type.
        """
        if self.field_type:
            values = []
            for value in raw_value:
                try:
                    values.append(self.field_type(value))
                except ValueError:
                    logger.error(
                        "Could not convert value '%s' to type '%s', so the raw value has been used",
                        value,
                        self.field_type,
                    )
                    values.append(value)
            return values

        return raw_value

    def process_facet_buckets(self, request, buckets):
        """
        Process the Elasticsearch facet buckets and update the field choices.

        Args:
            request (HttpRequest): The request object.
            buckets (list): The facet buckets from the Elasticsearch response.
        """
        choices = []
        for bucket in buckets:
            key, doc_count, _ = bucket
            choices.append((key, self.format_choice_label(request, key, doc_count)))
        self.choices = choices

    def format_choice_label(self, request, key, doc_count):
        """
        Format the choice label.

        Args:
            request (HttpRequest): The request object.
            key (str): The facet key.
            doc_count (int): The document count for the facet.

        Returns:
            str: The formatted choice label.
        """
        if self.formatter:
            return self.formatter(request, key, doc_count)
        return f"{key} ({doc_count})"


class TermsFacetField(FacetField):
    """
    A form field that renders Elasticsearch terms facets as checkboxes.
    """

    def get_es_facet(self):
        """
        Get the Elasticsearch terms facet.

        Returns:
            TermsFacet: The Elasticsearch terms facet.
        """
        return TermsFacet(field=self.es_field)


class RangeOption(dict):
    """
    A class representing a range option for range facets.

    Args:
        lower (int or float, optional): The lower bound of the range.
        upper (int or float, optional): The upper bound of the range.
        label (str, optional): The label for the range option.

    Raises:
        ValueError: If neither lower nor upper is provided.
    """

    def __init__(self, lower=None, upper=None, label=None):
        if not lower and not upper:
            raise ValueError("Either lower or upper must be provided")

        super().__init__({"from": lower, "to": upper, "label": label})


class RangeFacetField(FacetField):
    """
    A form field that renders Elasticsearch range facets as multiple choice fields.

    Args:
        es_field (str): The field name in the Elasticsearch index.
        field_type (type): The type of the field (e.g., int, str, bool).
        ranges (list): A list of range options.
        formatter (callable, optional): A function that formats the facet values.
        **kwargs: Additional keyword arguments for the field.
    """

    def __init__(self, es_field, field_type, ranges, formatter=None, **kwargs):
        self.ranges = self._parse_ranges(ranges)
        super().__init__(es_field, field_type, formatter, **kwargs)

    def _parse_ranges(self, ranges):
        """
        Parse the range options.

        Args:
            ranges (list): A list of range options.

        Returns:
            dict: A dictionary of range options.
        """

        def to_range_option(range_):
            return range_ if isinstance(range_, RangeOption) else RangeOption(**range_)

        return {
            f"{range_['from']}_{range_['to']}": to_range_option(range_)
            for range_ in ranges
        }

    def get_es_facet(self):
        """
        Get the Elasticsearch range facet.

        Returns:
            RangeFacet: The Elasticsearch range facet.
        """
        ranges = [
            (key, (range_.get("from"), range_.get("to")))
            for key, range_ in self.ranges.items()
        ]
        return RangeFacet(field=self.es_field, ranges=ranges)

    def process_facet_buckets(self, request, buckets):
        """
        Process the Elasticsearch facet buckets and update the field choices.

        Args:
            request (HttpRequest): The request object.
            buckets (list): The facet buckets from the Elasticsearch response.
        """
        choices = []
        for bucket in buckets:
            key, doc_count, _ = bucket
            if doc_count > 0:
                range_option = self.ranges.get(key)
                label = range_option.get("label", key) if range_option else key
                choices.append(
                    (key, self.format_choice_label(request, label, doc_count))
                )
        self.choices = choices


class FilterField:
    """
    A base class for form fields that filter Elasticsearch queries.
    """

    def get_es_filter_query(self, cleaned_data) -> Q:
        """
        Get the Elasticsearch filter query.

        Args:
            cleaned_data (dict): The cleaned data from the form.

        Returns:
            Q: The Elasticsearch filter query.

        Raises:
            NotImplementedError: If the method is not implemented in a subclass.
        """
        raise NotImplementedError(
            "You need to implement the method get_es_filter_query in your subclass."
        )


class SortField(forms.ChoiceField):
    """
    A form field for sorting in Elasticsearch queries.
    """

    def __init__(self, sort_choices, *args, **kwargs):
        """
        Initialize the SortField.

        Args:
            sort_choices (list): A list of tuples representing sorting options (value, label, elasticsearch sort).
            *args: Positional arguments for the field.
            **kwargs: Keyword arguments for the field.
        """
        choices = [(value, label) for value, label, _ in sort_choices]
        super().__init__(*args, **kwargs)
        self.choices = choices
        self.sort_mapping = {value: sort_field for value, _, sort_field in sort_choices}
