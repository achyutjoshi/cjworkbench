import asyncio
from collections import namedtuple
import datetime
from functools import partial
import importlib
import importlib.abc
import importlib.util
import inspect
import logging
import os
import sys
import time
import traceback
from types import ModuleType
from typing import Any, Awaitable, Callable, Dict, Optional
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
import pandas as pd
from .module_version import ModuleVersion
from .Params import Params
from .param_field import ParamDTypeDict
from ..modules.types import ProcessResult
from ..modules.countbydate import CountByDate
from ..modules.formula import Formula
from ..modules.loadurl import LoadURL
from ..modules.pastecsv import PasteCSV
import server.modules.pythoncode
import server.modules.refine
from ..modules.selectcolumns import SelectColumns
from ..modules.twitter import Twitter
from ..modules.uploadfile import UploadFile
from ..modules.googlesheets import GoogleSheets
from ..modules.editcells import EditCells
from ..modules.urlscraper import URLScraper
from ..modules.scrapetable import ScrapeTable
from ..modules.sortfromtable import SortFromTable
from ..modules.reordercolumns import ReorderFromTable
from ..modules.renamecolumns import RenameFromTable
from ..modules.duplicatecolumn import DuplicateColumn
from ..modules.joinurl import JoinURL
from ..modules.concaturl import ConcatURL
from server import minio


logger = logging.getLogger(__name__)


MockModule = namedtuple('MockModule', ['render'])


StaticModules = {
    'concaturl': ConcatURL,
    'countbydate': CountByDate,
    'duplicate-column': DuplicateColumn,
    'editcells': EditCells,
    'formula': Formula,
    'googlesheets': GoogleSheets,
    'joinurl': JoinURL,
    'loadurl': LoadURL,
    'pastecsv': PasteCSV,
    'pythoncode': server.modules.pythoncode,
    'refine': server.modules.refine,
    'rename-columns': RenameFromTable,
    'reorder-columns': ReorderFromTable,
    'scrapetable': ScrapeTable,
    'selectcolumns': SelectColumns,
    'sort-from-table': SortFromTable,
    'twitter': Twitter,
    'uploadfile': UploadFile,
    'urlscraper': URLScraper,
}


def _default_render(param1, param2,
                    *, fetch_result, **kwargs) -> ProcessResult:
    """Render fetch_result or pass-through input."""
    if fetch_result is not None:
        return fetch_result
    else:
        # Pass-through input.
        #
        # Internal and external modules have opposite calling conventions: one
        # takes (params, table) and the other takes (table, params). Return
        # whichever input is a pd.DataFrame.
        if isinstance(param1, pd.DataFrame):
            return ProcessResult(param1)
        else:
            return ProcessResult(param2)


async def _default_fetch(params, **kwargs) -> Optional[ProcessResult]:
    """No-op fetch."""
    return None


class DeletedModule:
    def render(self, params: Params, table: Optional[pd.DataFrame],
               fetch_result: Optional[ProcessResult]) -> ProcessResult:
        logger.info('render() deleted module')
        return ProcessResult(error='Cannot render: module was deleted')

    async def fetch(
        self,
        params: Params,
        *,
        workflow_id: int,
        get_input_dataframe: Callable[[], Awaitable[pd.DataFrame]],
        get_stored_dataframe: Callable[[], Awaitable[pd.DataFrame]],
        get_workflow_owner: Callable[[], Awaitable[User]]
    ) -> ProcessResult:
        logger.info('fetch() deleted module')
        return ProcessResult(error='Cannot fetch: module was deleted')


class LoadedModule:
    """A module with `fetch` and `render` methods.
    """
    def __init__(self, module_id_name: str, version_sha1: str,
                 is_external: bool=True,
                 render_impl: Callable=_default_render,
                 fetch_impl: Callable=_default_fetch,
                 migrate_params_impl: Optional[Callable]=None):
        self.module_id_name = module_id_name
        self.version_sha1 = version_sha1
        self.is_external = is_external
        self.name = f'{module_id_name}:{version_sha1}'
        self.render_impl = render_impl
        self.fetch_impl = fetch_impl
        self.migrate_params_impl = migrate_params_impl

    def _wrap_exception(self, err) -> ProcessResult:
        """Coerce an Exception (must be on the stack) into a ProcessResult."""
        # Catch exceptions in the module render function, and return
        # error message + line number to user
        exc_name = type(err).__name__
        exc_type, exc_obj, exc_tb = sys.exc_info()
        # [1] = where the exception ocurred, not the render()
        tb = traceback.extract_tb(exc_tb)[1]
        fname = os.path.split(tb[0])[1]
        lineno = tb[1]

        error = f'{exc_name}: {str(err)} at line {lineno} of {fname}'
        return ProcessResult(error=error)

    def render(self, params: Params,
               table: Optional[pd.DataFrame],
               fetch_result: Optional[ProcessResult]) -> ProcessResult:
        """
        Process `table` with module `render` method, for a ProcessResult.

        If the `render` method raises an exception, this method will return an
        error string. It is always an error for a module to raise an exception.

        Exceptions become error messages. This method cannot produce an
        exception.

        This synchronous method can be slow for complex modules or large
        datasets. Consider calling it from an executor.
        """
        # Internal and external modules have different calling conventions
        if self.is_external:
            arg1, arg2 = (table, params.to_painful_dict(table))
        else:
            arg1, arg2 = (params, table)

        kwargs = {}
        spec = inspect.getfullargspec(self.render_impl)
        varkw = bool(spec.varkw)  # if True, function accepts **kwargs
        kwonlyargs = spec.kwonlyargs
        if varkw or 'fetch_result' in kwonlyargs:
            kwargs['fetch_result'] = fetch_result

        time1 = time.time()

        try:
            out = self.render_impl(arg1, arg2, **kwargs)
        except Exception as err:
            logger.exception('Exception in %s.render', self.module_id_name)
            out = self._wrap_exception(err)

        try:
            out = ProcessResult.coerce(out)
        except Exception as err:
            logger.exception('Exception coercing %s.render output',
                             self.module_id_name)
            out = self._wrap_exception(err)

        out.truncate_in_place_if_too_big()
        out.sanitize_in_place()

        time2 = time.time()
        shape = out.dataframe.shape if out is not None else (-1, -1)
        logger.info('%s rendered (%drows,%dcols)=>(%drows,%dcols) in %dms',
                    self.name, table.shape[0], table.shape[1],
                    shape[0], shape[1], int((time2 - time1) * 1000))

        return out

    async def fetch(
        self,
        params: Params,
        *,
        workflow_id: int,
        get_input_dataframe: Callable[[], Awaitable[pd.DataFrame]],
        get_stored_dataframe: Callable[[], Awaitable[pd.DataFrame]],
        get_workflow_owner: Callable[[], Awaitable[User]]
    ) -> ProcessResult:
        """
        Process `params` with module `fetch` method, to build a ProcessResult.

        If the `fetch` method raises an exception, this method will return an
        error string. It is always an error for a module to raise an exception.
        """
        kwargs = {}
        spec = inspect.getfullargspec(self.fetch_impl)
        varkw = bool(spec.varkw)  # if True, function accepts **kwargs
        kwonlyargs = spec.kwonlyargs
        if varkw or 'workflow_id' in kwonlyargs:
            kwargs['workflow_id'] = workflow_id
        if varkw or 'get_input_dataframe' in kwonlyargs:
            kwargs['get_input_dataframe'] = get_input_dataframe
        if varkw or 'get_stored_dataframe' in kwonlyargs:
            kwargs['get_stored_dataframe'] = get_stored_dataframe
        if varkw or 'get_workflow_owner' in kwonlyargs:
            kwargs['get_workflow_owner'] = get_workflow_owner

        if self.is_external:
            # Pass input to params.to_painful_dict().
            input_dataframe_future = get_input_dataframe()

            input_dataframe = await input_dataframe_future
            if input_dataframe is None:
                input_dataframe = pd.DataFrame()
            params = params.to_painful_dict(input_dataframe)
            # If we're passing get_input_dataframe via kwargs, short-circuit it
            # because we already know the result.
            if 'get_input_dataframe' in kwargs:
                kwargs['get_input_dataframe'] = lambda: input_dataframe_future

        time1 = time.time()

        if inspect.iscoroutinefunction(self.fetch_impl):
            future_result = self.fetch_impl(params, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            func = partial(self.fetch_impl, params, **kwargs)
            future_result = loop.run_in_executor(None, func)

        try:
            out = await future_result
        except Exception as err:
            logger.exception('Exception in %s.fetch', self.module_id_name)
            out = self._wrap_exception(err)

        time2 = time.time()

        if out is None:
            shape = (-1, -1)
        else:
            out = ProcessResult.coerce(out)
            out.truncate_in_place_if_too_big()
            out.sanitize_in_place()
            shape = out.dataframe.shape

        logger.info('%s fetched =>(%drows,%dcols) in %dms',
                    self.name, shape[0], shape[1],
                    int((time2 - time1) * 1000))

        return out

    @classmethod
    @database_sync_to_async
    def for_module_version(cls,
                           module_version: ModuleVersion) -> 'LoadedModule':
        """
        Return module referenced by `module_version` (asynchronously).

        We assume:

        * the ModuleVersion and Module are in the database (foreign keys prove
          this)
        * external-module files exist on disk
        * external-module files were validated before being written to database
        * external-module files haven't changed
        * external-module files' dependencies are in PYTHONPATH
        * external-module files' dependencies haven't changed (i.e., imports)

        Invalid assumption? Fix the bug elsewhere.
        """
        return cls.for_module_version_sync(module_version)

    def migrate_params(self, schema: ParamDTypeDict,
                       values: Dict[str, Any]) -> Dict[str, Any]:
        if self.migrate_params_impl is not None:
            try:
                values = self.migrate_params_impl(values)
            except Exception as err:
                raise ValueError(err)

            try:
                schema.validate(values)
            except ValueError as err:
                raise ValueError('migrate_params() gave bad output: %s',
                                 str(err))

            return values
        else:
            return schema.coerce(values)

    @classmethod
    def for_module_version_sync(
        cls,
        module_version: Optional[ModuleVersion]
    ) -> 'LoadedModule':
        """
        Return module referenced by `module_version`.

        We assume:

        * if `module_version is not None`, then its `module` is in the database
        * external-module files exist on disk
        * external-module files were validated before being written to database
        * external-module files haven't changed
        * external-module files' dependencies are in PYTHONPATH
        * external-module files' dependencies haven't changed (i.e., imports)

        Invalid assumption? Fix the bug elsewhere.

        Do not call this from an async method, because you may leak a database
        connection. Use `for_module_version` instead.
        """
        if module_version is None:
            return DeletedModule()

        module_id_name = module_version.id_name
        version_sha1 = module_version.source_version_hash

        try:
            module = StaticModules[module_id_name]
            version_sha1 = 'internal'
            is_external = False
        except KeyError:
            module = load_external_module(module_id_name, version_sha1,
                                          module_version.last_update_time)
            is_external = True

        render_impl = getattr(module, 'render', _default_render)
        fetch_impl = getattr(module, 'fetch', _default_fetch)
        migrate_params_impl = getattr(module, 'migrate_params', None)

        return cls(module_id_name, version_sha1, is_external=is_external,
                   render_impl=render_impl, fetch_impl=fetch_impl,
                   migrate_params_impl=migrate_params_impl)


def _is_basename_python_code(key: str) -> bool:
    """
    True iff the given filename is a module's Python code file.

    >>> _is_basename_python_code('filter.py')
    True
    >>> _is_basename_python_code('filter.json')  # not Python
    True
    >>> _is_basename_python_code('setup.py')  # setup.py is an exception
    False
    >>> _is_basename_python_code('test_filter.py')  # tests are exceptions
    False
    """
    if key == 'setup.py':
        return False
    if key.startswith('test_'):
        return False
    return key.endswith('.py')


class TempfileLoader(importlib.abc.SourceLoader):
    def __init__(self, tf):
        with open(tf.name, 'rb') as f:
            self._data = f.read()
        self._name = tf.name

    def get_data(self, *args):
        return self._data

    def get_filename(self, *args):
        return self._name


def _load_external_module_uncached(module_id_name: str,
                                   version_sha1: str) -> ModuleType:
    """
    Load a Python Module given a name and version.
    """
    prefix = '%s/%s/' % (module_id_name, version_sha1)
    all_keys = minio.list_file_keys(minio.ExternalModulesBucket, prefix)
    python_code_key = next(k for k in all_keys
                           if _is_basename_python_code(k[len(prefix):]))

    with minio.temporarily_download(minio.ExternalModulesBucket,
                                    python_code_key) as tf:
        # Now we can load the code into memory.
        name = '%s.%s' % (module_id_name, version_sha1)
        logger.info(f'Loading {name} from {tf.name}')
        spec = importlib.util.spec_from_file_location(
            name,
            tf.name,
            loader=TempfileLoader(tf)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    return module


def load_external_module(module_id_name: str, version_sha1: str,
                         last_update_time: datetime.datetime) -> ModuleType:
    """
    Load a Python Module given a name and version.

    This is memoized: for each module_id_name, the latest
    (version_sha1, last_update_time) is kept in memory to speed up future
    calls. (It's common during development for `version_sha1` to stay
    `develop`, though `last_update_time` changes frequently. We want to reload
    the module each time that happens.)

    Assume:

    * the files exist on disk and are valid
    * the files never change
    * the files' dependencies are in our PYTHONPATH
    * the files' dependencies haven't changed (i.e., its imports)

    ... in short: this function shouldn't raise an error.
    """
    cache = load_external_module._cache
    cache_condition = (version_sha1, last_update_time)
    cached_condition, cached_value = cache.get(module_id_name, (None, None))

    if cached_condition == cache_condition:
        return cached_value

    value = _load_external_module_uncached(module_id_name, version_sha1)
    cache[module_id_name] = (cache_condition, value)
    return value


load_external_module._cache = {}
load_external_module.cache_clear = load_external_module._cache.clear


def module_get_html_bytes(module_version: ModuleVersion) -> Optional[bytes]:
    prefix = '%s/%s/' % (module_version.id_name,
                         module_version.source_version_hash)
    all_keys = minio.list_file_keys(minio.ExternalModulesBucket, prefix)
    try:
        html_key = next(k for k in all_keys if k.endswith('.html'))
    except StopIteration:
        return None  # there is no HTML file

    with minio.open_for_read(minio.ExternalModulesBucket, html_key) as f:
        return f.read()
