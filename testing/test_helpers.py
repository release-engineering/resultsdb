import datetime
import pytest

import resultsdb.controllers.api_v2 as apiv2


class MyRequest(object):

    def __init__(self, url):
        self.url = url


class TestDictOrStringType():

    def test_dict_or_string_type(self):
        assert apiv2.dict_or_string_type('') == ''
        assert apiv2.dict_or_string_type(u'') == u''
        assert apiv2.dict_or_string_type({}) == {}
        with pytest.raises(ValueError):
            apiv2.dict_or_string_type([])


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


class TestGetResultsParseArgs():
    # TODO: write something!
    pass
