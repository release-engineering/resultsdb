import datetime
import pytest
import functools

import resultsdb.controllers.api_v2 as apiv2
import resultsdb.lib.helpers as helpers
import resultsdb.messaging as messaging


class MyRequest(object):

    def __init__(self, url):
        self.url = url


class TestTypeHelpers():

    def test_dict_or_string(self):
        assert helpers.dict_or_string('') == ''
        assert helpers.dict_or_string(u'') == u''
        assert helpers.dict_or_string({}) == {}
        assert helpers.dict_or_string({"foo": "bar"}) == {"foo": "bar"}
        with pytest.raises(ValueError):
            helpers.dict_or_string([])

    def test_list_or_none(self):
        assert helpers.list_or_none(None) is None
        assert helpers.list_or_none([]) == []
        assert helpers.list_or_none(["foo", "bar"]) == ["foo", "bar"]
        with pytest.raises(ValueError):
            assert helpers.list_or_none("")

    def test_non_empty(self):
        assert helpers.non_empty(basestring, "foobar") == "foobar"
        assert helpers.non_empty(int, 0) == 0
        assert helpers.non_empty(int, 1) == 1
        assert helpers.non_empty(float, 0.0) == 0.0
        assert helpers.non_empty(float, 1.0) == 1.0
        assert helpers.non_empty(list, ["foo"]) == ["foo"]
        assert helpers.non_empty(dict, {"foo": "bar"}) == {"foo": "bar"}

        with pytest.raises(ValueError):
            helpers.non_empty(basestring, "")
        with pytest.raises(ValueError):
            helpers.non_empty(list, [])
        with pytest.raises(ValueError):
            helpers.non_empty(dict, {})

    def test_non_empty_with_lambda(self):
        assert helpers.non_empty(helpers.list_or_none, ['foo']) == ['foo']
        assert helpers.non_empty(functools.partial(helpers.non_empty, helpers.list_or_none), ['foo']) == ['foo']
        with pytest.raises(ValueError):
            helpers.non_empty(helpers.list_or_none, [])
        with pytest.raises(ValueError):
            helpers.non_empty(helpers.list_or_none, None)
        with pytest.raises(ValueError):
            helpers.non_empty(functools.partial(helpers.non_empty, helpers.list_or_none), [])


class TestExtraDataValidation():
    def test__validate_create_result_extra_data(self):
        data = {"foobar": 0, "moo": "1"}
        assert apiv2._validate_create_result_extra_data(None, data) == data
        assert apiv2._validate_create_result_extra_data([], data) == data
        assert apiv2._validate_create_result_extra_data(['foobar'], data) == data
        assert apiv2._validate_create_result_extra_data(['moo'], data) == data
        with pytest.raises(ValueError):
            apiv2._validate_create_result_extra_data(['foobar'], None)
        with pytest.raises(ValueError):
            apiv2._validate_create_result_extra_data(['foobar'], {})
        with pytest.raises(ValueError):
            apiv2._validate_create_result_extra_data(['foobar'], {'foobar': None})
        with pytest.raises(ValueError):
            apiv2._validate_create_result_extra_data(['foobar'], {'foobar': ''})
        with pytest.raises(ValueError):
            apiv2._validate_create_result_extra_data(None, "")


class TestPrevNextURL():

    def setup_method(self, method):
        self.rq = MyRequest(url='')

    def test_no_data_no_page_in_url(self, monkeypatch):
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls([], 1)
        assert data == []
        assert prev is None
        assert next is None

    def test_no_data_page_in_url(self, monkeypatch):
        self.rq.url = '?page=0'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls([], 1)
        assert data == []
        assert prev is None
        assert next is None

    def test_data_no_page_in_url(self, monkeypatch):
        self.rq.url = 'URL'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev is None
        assert next == 'URL?page=1'

    def test_data_no_page_in_url_stuff_in_url(self, monkeypatch):
        self.rq.url = 'URL?stuff=some'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev is None
        assert next == 'URL?stuff=some&page=1'

    def test_data_page_and_limit_in_url(self, monkeypatch):
        self.rq.url = 'URL?page=1&limit=1'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev == 'URL?page=0&limit=1'
        assert next == 'URL?page=2&limit=1'

        self.rq.url = 'URL?limit=1&page=1'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev == 'URL?limit=1&page=0'
        assert next == 'URL?limit=1&page=2'

        self.rq.url = 'URL&page=1&limit=1'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev == 'URL&page=0&limit=1'
        assert next == 'URL&page=2&limit=1'

        self.rq.url = 'URL&limit=1&page=1'
        monkeypatch.setattr(apiv2, 'request', self.rq)

        data, prev, next = apiv2.prev_next_urls(range(10), 1)
        assert data == [0]
        assert prev == 'URL&limit=1&page=0'
        assert next == 'URL&limit=1&page=2'

class TestParseSince():

    def setup_method(self, method):
        self.date_str = '2016-01-01T01:02:03.04'
        self.date_obj = datetime.datetime.strptime(self.date_str, "%Y-%m-%dT%H:%M:%S.%f")

    def test_parse_start(self):
        start, end = apiv2.parse_since(self.date_str)
        assert start == self.date_obj
        assert end is None

    def test_parse_start_with_timezone_info(self):
        start, end = apiv2.parse_since(self.date_str + 'Z')
        assert start == self.date_obj
        assert end is None

        start, end = apiv2.parse_since(self.date_str + '+01')
        assert start == self.date_obj
        assert end is None

    def test_parse_end(self):
        start, end = apiv2.parse_since(self.date_str + ',' + self.date_str)
        assert start == self.date_obj
        assert end == self.date_obj


class TestMessaging():

    def test_load_plugin(self):
        plugin = messaging.load_messaging_plugin('dummy', {})
        assert isinstance(plugin, messaging.DummyPlugin)
        try:
            plugin = messaging.load_messaging_plugin('fedmsg', {})
        except KeyError as err:
            if "not found" in err.message:
                print """=============== HINT ===============
This exception can be caused by the fact, that you did not run
`python setup.py develop` before executing the testsuite.

The messaging plugins are defined as setuptools entry-points, and those live in the
.egg-info directory. If you're developing locally, that directory is usually present
in pwd due to `python setup.py develop`.

If you ran `python setup.py develop` and are still seeing this error, then:
 - you might me missing the 'fedmsg' entrypoint in setup.py
 - there can be an error in the plugin loading code"""
            raise
        assert isinstance(plugin, messaging.FedmsgPlugin), "check whether `fedmsg` entrypoint in setup.py points to resultsdb.messaging:FedmsgPlugin"


class TestGetResultsParseArgs():
    # TODO: write something!
    pass
