import re
from typing import Any, Dict, FrozenSet, List, Optional, Set


class ParamDType:
    """
    Data type -- that is, storage format -- for a parameter.

    Parameter values are always stored as JSON values. A parameter's DType is
    the JSON "schema" for its values.

    This type applies to user-input data. Since the user may input _anything_
    (even invalid data, especially across multiple versions of a module), we
    provide `coerce()` and `validate()` to ensure type-safety.

    This is the abstract base class for a variety of DTypes which can represent recursive
    type structures.
    """

    def coerce(self, value: Any) -> Any:
        """
        Convert `value` to something valid.

        This cannot raise: it must return _something_ instead. In effect, types
        must have sensible "zero" values (e.g., a String's zero value is "").
        """
        raise NotImplementedError

    def validate(self, value: Any) -> Any:
        """
        Raise `ValueError` if `value` is not valid.
        """
        raise NotImplementedError

    def iter_dfs_dtypes(self):
        """
        Depth-first search to yield dtypes.

        By default, this yields `self`. "Container"-style dtypes should
        override this method to yield `self` and then yield each "child"
        `dtype`.
        """
        yield self

    def iter_dfs_dtype_values(self, value: Any):
        """
        Depth-first search to yield (dtype, value) pairs.

        By default, this yields `(self, value)`. "Container"-style dtypes
        should override this method to yield `(self, value)` and then yield
        each "child" `(dtype, value)`.

        Be sure to coerce() or validate() `value` before passing it here.
        """
        yield (self, value)

    def find_leaf_values_with_dtype(self, dtype: type, value: Any) -> FrozenSet[Any]:
        """
        Recurse through `value`, finding sub-values of type `dtype`.

        Be sure to coerce() or validate() `value` before passing it here.

        "Container"-style dtypes should override this method to walk their
        children.

        Example:

        >>> schema = ParamDTypeList(inner_dtype=ParamDTypeTab())
        >>> tab_slugs = schema.find_leaf_values_with_dtype(
        ...     ParamDTypeTab,
        ...     ['tab-123', 'tab-234']
        ... })
        {'tab-123', 'tab-234'}
        """
        return frozenset(v for dt, v in self.iter_dfs_dtype_values(value)
                         if isinstance(dt, dtype))

    def omit_missing_table_columns(self, value: Any, columns: Set[str]) -> Any:
        """
        Recursively nix `value`'s column references that aren't in `columns`.

        For example: remove any `ParamDTypeColumn` nested within a
        `ParamDTypeList` if that column value isn't in `columns`.

        Assumes `value` is valid.

        This is almost DEPRECATED because it's a visitor and the visitor
        pattern is a better fit. We only use it in Params.to_painful_dict(),
        which itself is almost DEPRECATED. When Params.to_painful_dict() is
        finally nixed, nix this method. In the meantime, prefer
        renderprep.clean_value(): the logic is better there because there's
        clear intent.
        """
        # default implementation: no-op. Most dtypes aren't nested or columnar
        return value

    @classmethod
    def _from_plain_data(cls, **kwargs):
        """
        Virtual method used by `ParamDType.parse()`

        `kwargs` are JSON keys/values.
        """
        return cls(**kwargs)

    @classmethod
    def parse(cls, json_value):
        """
        Deserialize this DType from JSON.

        Currently, we only JSON-serialize DTypes in module specifications that
        have explicit `param_schema`. That's rare.
        """
        json_value = json_value.copy()  # don't alter input
        json_type = json_value.pop('type')
        dtype = cls.JsonTypeToDType[json_type]
        return dtype._from_plain_data(**json_value)  # sans 'type'


class ParamDTypeString(ParamDType):
    """
    Valid Unicode text.

    This is stricter than Python `str`. In particular, `"\\ud8002"` is invalid
    (because a lone surrogate isn't valid Unicode text) and `"\x00"` is invalid
    (because Postgres doesn't allow null bytes).
    """
    InvalidCodePoints = re.compile('[\u0000\ud800-\udfff]')

    def __init__(self, default=''):
        super().__init__()
        self.default = default

    def __repr__(self):
        return 'ParamDTypeString()'

    def coerce(self, value):
        if value is None:
            return self.default
        elif not isinstance(value, str):
            try:
                value = str(value)
            except Exception:  # __str__() has 1,000 ways to fail....
                return self.default

        # `value` may still be invalid Unicode. In particular, if we received a
        # value from json.parse() it can have invalid surrogates, because
        # invalid surrogates are valid in JSON Strings (!).
        return ParamDTypeString.InvalidCodePoints.sub('\ufffd', value)

    def validate(self, value):
        if not isinstance(value, str):
            raise ValueError('Value %r is not a string' % value)
        if ParamDTypeString.InvalidCodePoints.search(value) is not None:
            if '\x00' in value:
                raise ValueError(
                    'Value %r is not valid text: zero byte not allowed'
                    % value
                )
            else:
                raise ValueError(
                    'Value %r is not valid Unicode: surrogates not allowed'
                    % value
                )


class ParamDTypeInteger(ParamDType):
    def __init__(self, default=0):
        super().__init__()
        self.default = default

    def __repr__(self):
        return 'ParamDTypeInteger()'

    def coerce(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return self.default

    def validate(self, value):
        if not isinstance(value, int):
            raise ValueError('Value %r is not an integer' % value)


class ParamDTypeFloat(ParamDType):
    """
    Accepts floats or integers. Akin to JSON 'number' type.
    """
    def __init__(self, default=0.0):
        super().__init__()
        self.default = default

    def __repr__(self):
        return 'ParamDTypeFloat()'

    def coerce(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return self.default

    def validate(self, value):
        if not (isinstance(value, float) or isinstance(value, int)):
            raise ValueError('Value %r is not a float' % value)

    @classmethod
    def _from_plain_data(cls, default=0.0):
        # JSON won't differentiate between int and float
        default = float(default)
        return cls(default=default)


class ParamDTypeBoolean(ParamDType):
    def __init__(self, default=False):
        super().__init__()
        self.default = default

    def __repr__(self):
        return 'ParamDTypeBoolean()'

    def coerce(self, value):
        if value is None:
            return self.default
        elif isinstance(value, str):
            return value.lower() == 'true'
        else:
            try:
                return bool(value)
            except (TypeError, ValueError):
                return self.default

    def validate(self, value):
        if not isinstance(value, bool):
            raise ValueError('Value %r is not a boolean' % value)


class ParamDTypeColumn(ParamDTypeString):
    def __init__(self, column_types: Optional[FrozenSet[str]] = None,
                 tab_parameter: Optional[str] = None):
        super().__init__()
        self.column_types = column_types
        self.tab_parameter = tab_parameter

    def __repr__(self):
        return 'ParamDTypeColumn' + repr((self.column_types,
                                          self.tab_parameter))

    def omit_missing_table_columns(self, value, columns):
        if value not in columns:
            return ''
        else:
            return value

    @classmethod
    def _from_plain_data(cls, *, column_types=None, **kwargs):
        if column_types:
            # column_types comes from JSON as a list. We need a set.
            kwargs['column_types'] = frozenset(column_types)
        return cls(**kwargs)


class ParamDTypeMulticolumn(ParamDType):
    def __init__(self, column_types: Optional[FrozenSet[str]] = None,
                 tab_parameter: Optional[str] = None):
        super().__init__()
        self.column_types = column_types
        self.tab_parameter = tab_parameter

    def __repr__(self):
        return 'ParamDTypeMulticolumn' + repr((self.column_types,
                                               self.tab_parameter))

    def omit_missing_table_columns(self, value, columns):
        return [c for c in value if c in columns]

    def coerce(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            value = list(value)
        return [str(v) for v in value]

    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError('Value %r is not a list' % value)
        for i, v in enumerate(value):
            if not isinstance(v, str):
                raise ValueError('Item %d of value %r is not a string'
                                 % (i, value))

    @classmethod
    def _from_plain_data(cls, *, column_types=None, **kwargs):
        if column_types:
            # column_types comes from JSON as a list. We need a set.
            kwargs['column_types'] = frozenset(column_types)
        return cls(**kwargs)


class ParamDTypeEnum(ParamDType):
    def __init__(self, choices: FrozenSet[Any], default: Any):
        super().__init__()
        if default not in choices:
            raise ValueError(
                'Default %(default)r is not in choices %(choices)r'
                % {'default': default, 'choices': choices}
            )
        self.choices = choices
        self.default = default

    def __repr__(self):
        return 'ParamDTypeEnum' + repr((self.choices, self.default))

    def coerce(self, value):
        if value in self.choices:
            return value
        else:
            return self.default

    def validate(self, value):
        if value not in self.choices:
            raise ValueError(
                'Value %(value)r is not in choices %(choices)r'
                % {'value': value, 'choices': self.choices}
            )

    @classmethod
    def _from_plain_data(cls, *, choices: List[str], **kwargs):
        return cls(choices=frozenset(choices), **kwargs)


class ParamDTypeList(ParamDType):
    def __init__(self, inner_dtype: ParamDType, default=[]):
        super().__init__()
        self.inner_dtype = inner_dtype
        self.default = default

    def __repr__(self):
        return 'ParamDTypeList' + repr((self.inner_dtype,))

    def coerce(self, value):
        if value is None:
            return self.default

        if not hasattr(value, '__iter__'):
            value = [value]

        return [self.inner_dtype.coerce(v) for v in value]

    def validate(self, value):
        if not isinstance(value, list):
            raise ValueError('Value %r is not a list' % value)

        for v in value:
            self.inner_dtype.validate(v)

    # override
    def iter_dfs_dtypes(self):
        yield from super().iter_dfs_dtypes()
        yield self.inner_dtype

    # override
    def iter_dfs_dtype_values(self, value):
        yield from super().iter_dfs_dtype_values(value)
        for v in value:
            yield from self.inner_dtype.iter_dfs_dtype_values(v)

    def omit_missing_table_columns(self, value, columns):
        return [self.inner_dtype.omit_missing_table_columns(v, columns)
                for v in value]

    @classmethod
    def _from_plain_data(cls, *, inner_dtype, **kwargs):
        inner_dtype = cls.parse(inner_dtype)
        return cls(inner_dtype=inner_dtype, **kwargs)


class ParamDTypeDict(ParamDType):
    """
    A grouping of properties with a schema defined in the dtype.

    This is different from ParamDTypeMap, which allows arbitrary keys and
    forces all values to have the same dtype.
    """
    def __init__(self, properties: Dict[str, ParamDType], default=None):
        super().__init__()
        self.properties = properties
        if default is None:
            default = dict((name, dtype.coerce(None))
                           for name, dtype in self.properties.items())
        self.default = default

    def __repr__(self):
        return 'ParamDTypeDict' + repr((self.properties,))

    def coerce(self, value):
        if not isinstance(value, dict):
            return self.default

        return dict((name, dtype.coerce(value.get(name)))
                    for name, dtype in self.properties.items())

    def validate(self, value):
        if not isinstance(value, dict):
            raise ValueError('Value %r is not a dict' % value)

        expect_keys = set(self.properties.keys())
        actual_keys = set(value.keys())
        if expect_keys != actual_keys:
            raise ValueError(
                'Value %(value)r has wrong names: expected names %(names)r'
                % {'value': value, 'names': expect_keys}
            )

        for name, dtype in self.properties.items():
            dtype.validate(value[name])

    # override
    def iter_dfs_dtypes(self):
        yield from super().iter_dfs_dtypes()
        yield from self.properties.values()

    # override
    def iter_dfs_dtype_values(self, value):
        yield from super().iter_dfs_dtype_values(value)
        for name, dtype in self.properties.items():
            yield from dtype.iter_dfs_dtype_values(value[name])

    def omit_missing_table_columns(self, value, columns):
        return dict(
            (k, self.properties[k].omit_missing_table_columns(v, columns))
            for k, v in value.items()
        )

    @classmethod
    def _from_plain_data(cls, *, properties, **kwargs):
        properties = dict((k, cls.parse(v)) for k, v in properties.items())
        return cls(properties=properties, **kwargs)


class ParamDTypeMap(ParamDType):
    """
    A key-value store with arbitrary string keys and all-the-same-dtype values.

    This is different from ParamDTypeDict, which has dtype-defined properties,
    each with its own dtype.
    """
    def __init__(self, value_dtype: ParamDType, default={}):
        super().__init__()
        self.value_dtype = value_dtype
        self.default = default

    def __repr__(self):
        return 'ParamDTypeMap' + repr((self.value_dtype, self.default))

    def coerce(self, value):
        if not isinstance(value, dict):
            return self.default

        return dict((k, self.value_dtype.coerce(v)) for k, v in value.items())

    def validate(self, value):
        if not isinstance(value, dict):
            raise ValueError('Value %r is not a dict' % value)

        for _, v in value.items():
            self.value_dtype.validate(v)

    # override
    def iter_dfs_dtypes(self):
        yield from super().iter_dfs_dtypes()
        yield self.value_dtype

    # override
    def iter_dfs_dtype_values(self, value):
        yield from super().iter_dfs_dtype_values(value)
        for v in value.values():
            yield from self.value_dtype.iter_dfs_dtype_values(v)

    def omit_missing_table_columns(self, value, columns):
        return dict(
            (k, self.value_dtype.omit_missing_table_columns(v, columns))
            for k, v in value.items()
        )

    @classmethod
    def _from_plain_data(cls, *, value_dtype, **kwargs):
        value_dtype = cls.parse(value_dtype)
        return cls(value_dtype=value_dtype, **kwargs)


class ParamDTypeTab(ParamDTypeString):
    def __repr__(self):
        return 'ParamDTypeTab()'


class ParamDTypeMultitab(ParamDTypeList):
    """
    A 'tabs' parameter: a value is a list of tab slugs.

    This dtype behaves like a ParamDTypeList full of ParamDTypeTab values.
    We'll visit all child ParamDTypeTab values when walking a `value`.
    """

    def __init__(self, default=[]):
        super().__init__(inner_dtype=ParamDTypeTab(), default=default)

    def __repr__(self):
        return 'ParamDTypeMultitab()'

    # coerce(): ParamDTypeList will do what we want
    # validate(): ParamDTypeList will do what we want
    # iter_dfs_dtypes(): ParamDTypeList will do what we want
    # iter_dfs_dtype_values(): ParamDTypeList will do what we want

    # override
    @classmethod
    def _from_plain_data(cls, **kwargs):
        # don't require inner_dtype like ParamDTypeList does
        return cls(**kwargs)


class ParamDTypeMultichartseries(ParamDTypeList):
    """
    A 'y_series' parameter: array of columns+colors.

    This is like a List[Dict], except when omitting table columns we omit the
    entire Dict if its Column is missing.
    """

    def __init__(self, default=[]):
        super().__init__(inner_dtype=ParamDTypeDict({
            'column': ParamDTypeColumn(column_types=frozenset({'number'})),
            'color': ParamDTypeString(),  # TODO enforce '#abc123' pattern
        }), default=default)

    def __repr__(self):
        return 'ParamDTypeMultichartseries()'

    # coerce(): ParamDTypeList will do what we want
    # validate(): ParamDTypeList will do what we want
    # iter_dfs_dtypes(): ParamDTypeList will do what we want
    # iter_dfs_dtype_values(): ParamDTypeList will do what we want

    # override
    def omit_missing_table_columns(self, value, columns):
        series = super().omit_missing_table_columns(value, columns)
        # Omit each dict that has a missing column
        return [s for s in series if s['column']]

    # override
    @classmethod
    def _from_plain_data(cls, **kwargs):
        # don't require inner_dtype like ParamDTypeList does
        return cls(**kwargs)


class ParamDTypeFile(ParamDType):
    """
    String-encoded UUID pointing to an UploadedFile (and S3).

    The default, value, `null`, means "No file".
    """
    UUIDRegex = re.compile(
        r'\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z'
    )

    def __repr__(self):
        return 'ParamDTypeFile()'

    def coerce(self, value):
        try:
            self.validate(value)
        except ValueError:
            # If it's not a UUID, we _certainly_ can't repair it
            return None
        return value

    def validate(self, value):
        if value is None:
            return  # None is the default, and it's valid
        if not isinstance(value, str):
            raise ValueError('Value %r is not a string' % value)
        if not self.UUIDRegex.match(value):
            raise ValueError('Value %r is not a UUID string representation'
                             % value)


# Aliases to help with import. e.g.:
# from server.models.param_field import ParamDType
# dtype = ParamDType.String()
ParamDType.String = ParamDTypeString
ParamDType.Integer = ParamDTypeInteger
ParamDType.Float = ParamDTypeFloat
ParamDType.Boolean = ParamDTypeBoolean
ParamDType.Enum = ParamDTypeEnum
ParamDType.List = ParamDTypeList
ParamDType.Dict = ParamDTypeDict
ParamDType.Map = ParamDTypeMap
ParamDType.Column = ParamDTypeColumn
ParamDType.Multicolumn = ParamDTypeMulticolumn
ParamDType.Tab = ParamDTypeTab
ParamDType.Multitab = ParamDTypeMultitab
ParamDType.Multichartseries = ParamDTypeMultichartseries
ParamDType.File = ParamDTypeFile

ParamDType.JsonTypeToDType = {
    'string': ParamDTypeString,
    'integer': ParamDTypeInteger,
    'float': ParamDTypeFloat,
    'boolean': ParamDTypeBoolean,
    'enum': ParamDTypeEnum,
    'list': ParamDTypeList,
    'dict': ParamDTypeDict,
    'map': ParamDTypeMap,
    'tab': ParamDTypeTab,
    'tabs': ParamDTypeMultitab,
    'column': ParamDTypeColumn,
    'multicolumn': ParamDTypeMulticolumn,
    'multichartseries': ParamDTypeMultichartseries,
    'file': ParamDTypeFile,
}
