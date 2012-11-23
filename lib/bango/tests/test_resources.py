import json

from django.conf import settings

import mock
from nose.tools import eq_

from lib.sellers.models import (Seller, SellerBango, SellerProduct,
                                SellerProductBango)
from solitude.base import APITest

from ..client import ClientMock

import samples


class BangoAPI(APITest):
    api_name = 'bango'
    uuid = 'foo:uuid'

    def create(self):
        self.seller = Seller.objects.create(uuid=self.uuid)
        self.seller_bango = SellerBango.objects.create(seller=self.seller,
                                package_id=1, admin_person_id=3,
                                support_person_id=3, finance_person_id=4)
        self.seller_product = SellerProduct.objects.create(seller=self.seller)


@mock.patch.object(settings, 'BANGO_MOCK', True)
class TestPackageResource(BangoAPI):

    def setUp(self):
        super(TestPackageResource, self).setUp()
        self.list_url = self.get_list_url('package')

    def test_list_allowed(self):
        self.allowed_verbs(self.list_url, ['post'])

    def test_create(self):
        post = samples.good_address.copy()
        post['seller'] = ('/generic/seller/%s/' %
                          Seller.objects.create(uuid=self.uuid).pk)
        res = self.client.post(self.list_url, data=post)
        eq_(res.status_code, 201, res.content)
        seller_bango = SellerBango.objects.get()
        eq_(json.loads(res.content)['resource_pk'], seller_bango.pk)

    def test_missing_field(self):
        data = {'adminEmailAddress': 'admin@place.com',
                'supportEmailAddress': 'support@place.com'}
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 400, res.content)
        eq_(json.loads(res.content)['companyName'],
            ['This field is required.'])

    # TODO: probably should inject this in a better way.
    @mock.patch.object(ClientMock, 'mock_results')
    def test_bango_fail(self, mock_results):
        post = samples.good_address.copy()
        post['seller'] = ('/generic/seller/%s/' %
                          Seller.objects.create(uuid=self.uuid).pk)
        res = self.client.post(self.list_url, data=post)
        mock_results.return_value = {'responseCode': 'FAIL'}
        res = self.client.post(self.list_url, data=samples.good_address)
        eq_(res.status_code, 500)

    def test_get_allowed(self):
        self.create()
        url = self.get_detail_url('package', self.seller_bango.pk)
        self.allowed_verbs(url, ['get', 'patch'])

    def test_get(self):
        self.create()
        url = self.get_detail_url('package', self.seller_bango.pk)
        seller_bango = SellerBango.objects.get()
        data = json.loads(self.client.get(url).content)
        eq_(data['resource_pk'], seller_bango.pk)

    def test_patch(self):
        self.create()
        url = self.get_detail_url('package', self.seller_bango.pk)
        seller_bango = SellerBango.objects.get()
        old_support = seller_bango.support_person_id
        old_finance = seller_bango.finance_person_id

        res = self.client.patch(url, data={'supportEmailAddress': 'a@a.com'})
        eq_(res.status_code, 202, res.content)
        seller_bango = SellerBango.objects.get()

        # Check that support changed, but finance didn't.
        assert seller_bango.support_person_id != old_support
        eq_(seller_bango.finance_person_id, old_finance)


@mock.patch.object(settings, 'BANGO_MOCK', True)
class TestBangoProduct(BangoAPI):

    def setUp(self):
        super(TestBangoProduct, self).setUp()
        self.list_url = self.get_list_url('product')

    def test_list_allowed(self):
        self.allowed_verbs(self.list_url, ['post'])

    def test_create(self):
        self.create()
        data = samples.good_bango_number
        data['seller_product'] = ('/generic/product/%s/' %
                                  self.seller_product.pk)
        data['seller_bango'] = '/bango/package/%s/' % self.seller_bango.pk
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 201, res.content)

        obj = SellerProductBango.objects.get()
        eq_(obj.bango_id, 'some-bango-number')
        eq_(obj.seller_product_id, self.seller_bango.pk)


@mock.patch.object(settings, 'BANGO_MOCK', True)
class TestBangoMarkPremium(BangoAPI):

    def create(self):
        super(TestBangoMarkPremium, self).create()
        self.seller_product_bango = SellerProductBango.objects.create(
                                        seller_product=self.seller_product,
                                        seller_bango=self.seller_bango,
                                        bango_id='some-123')

    def test_list_allowed(self):
        self.allowed_verbs(self.list_url, ['post'])

    def setUp(self):
        super(TestBangoMarkPremium, self).setUp()
        self.list_url = self.get_list_url('make-premium')

    def test_mark(self):
        self.create()
        data = samples.good_make_premium.copy()
        data['seller_product_bango'] = ('/bango/product/%s/' %
                                        self.seller_product_bango.pk)
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 201)

    def test_fail(self):
        self.create()
        data = samples.good_make_premium.copy()
        data['currencyIso'] = 'FOO'
        data['seller_product_bango'] = ('/bango/product/%s/' %
                                        self.seller_product_bango.pk)
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 400)


@mock.patch.object(settings, 'BANGO_MOCK', True)
class TestBangoUpdateRating(BangoAPI):

    def create(self):
        super(TestBangoUpdateRating, self).create()
        self.seller_product_bango = SellerProductBango.objects.create(
                                        seller_product=self.seller_product,
                                        seller_bango=self.seller_bango,
                                        bango_id='some-123')

    def test_list_allowed(self):
        self.allowed_verbs(self.list_url, ['post'])

    def setUp(self):
        super(TestBangoUpdateRating, self).setUp()
        self.list_url = self.get_list_url('update-rating')

    def test_update(self):
        self.create()
        data = samples.good_update_rating.copy()
        data['seller_product_bango'] = ('/bango/product/%s/' %
                                        self.seller_product_bango.pk)
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 201, res.content)

    def test_fail(self):
        self.create()
        data = samples.good_update_rating.copy()
        data['rating'] = 'AWESOME!'
        data['seller_product_bango'] = ('/bango/product/%s/' %
                                        self.seller_product_bango.pk)
        res = self.client.post(self.list_url, data=data)
        eq_(res.status_code, 400, res.content)