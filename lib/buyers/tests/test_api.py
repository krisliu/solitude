import json
from datetime import datetime, timedelta

from django.conf import settings

import mock
from django_paranoia.signals import warning
from nose.tools import eq_

from lib.buyers.constants import BUYER_UUID_ALREADY_EXISTS, FIELD_REQUIRED
from lib.buyers.models import Buyer, BuyerPaypal
from solitude.base import APITest


class TestBuyer(APITest):

    def setUp(self):
        self.api_name = 'generic'
        self.uuid = 'sample:uid'
        self.pin = '1234'
        self.list_url = self.get_list_url('buyer')

    def test_add(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        eq_(Buyer.objects.filter(uuid=self.uuid).count(), 1)
        data = json.loads(res.content)
        eq_(data['pin'], True)

    def test_add_multiple(self):
        self.client.post(self.list_url, data={'uuid': self.uuid})
        res = self.client.post(self.list_url, data={'uuid': self.uuid})
        eq_(res.status_code, 400)
        eq_(self.get_errors(res.content, 'uuid'),
            [BUYER_UUID_ALREADY_EXISTS])

    def test_add_empty(self):
        res = self.client.post(self.list_url, data={'uuid': ''})
        eq_(res.status_code, 400)
        eq_(self.get_errors(res.content, 'uuid'), [FIELD_REQUIRED])

    def test_add_missing(self):
        res = self.client.post(self.list_url, data={})
        eq_(res.status_code, 400)
        eq_(self.get_errors(res.content, 'uuid'), [FIELD_REQUIRED])

    def test_list_allowed(self):
        self.allowed_verbs(self.list_url, ['post', 'get', 'put'])

    def test_filter(self):
        self.client.post(self.list_url, data={'uuid': self.uuid})
        res = self.client.get(self.list_url + '?uuid=%s' % self.uuid)
        eq_(res.status_code, 200)
        data = json.loads(res.content)
        eq_(data['meta']['total_count'], 1)
        eq_(data['objects'][0]['uuid'], self.uuid)

    def create(self, **kwargs):
        defaults = {'uuid': self.uuid, 'pin': self.pin}
        defaults.update(kwargs)
        return Buyer.objects.create(**defaults)

    def test_get(self):
        obj = self.create()
        res = self.client.get(self.get_detail_url('buyer', obj))
        eq_(res.status_code, 200)
        data = json.loads(res.content)
        eq_(data['uuid'], self.uuid)
        eq_(data['pin'], True)
        eq_(data['pin_failures'], 0)
        eq_(data['pin_is_locked_out'], False)
        eq_(data['pin_was_locked_out'], False)

    @mock.patch.object(settings, 'PIN_FAILURES', 1)
    def test_locked_out(self):
        obj = self.create()
        obj.incr_lockout()
        res = self.client.get(self.get_detail_url('buyer', obj))
        eq_(res.status_code, 200)
        data = json.loads(res.content)
        eq_(data['pin'], True)
        eq_(data['pin_failures'], 1)
        assert data['pin_is_locked_out']

    def test_not_patch_failures(self):
        obj = self.create()
        self.client.patch(self.get_detail_url('buyer', obj),
                          data={'pin_failures': 5, 'pin': '1234'})
        eq_(obj.reget().pin_failures, 0)

    def test_not_active(self):
        obj = self.create()
        obj.active = False
        obj.save()
        res = self.client.get(self.list_url, data={'active': True})
        eq_(json.loads(res.content)['meta']['total_count'], 0)

    def test_get_without_pin(self):
        obj = self.create(pin=None)
        res = self.client.get(self.get_detail_url('buyer', obj))
        eq_(res.status_code, 200)
        eq_(json.loads(res.content)['uuid'], self.uuid)
        data = json.loads(res.content)
        eq_(data['pin'], False)

    def test_detail_allowed_verbs(self):
        obj = self.create()
        self.allowed_verbs(self.get_detail_url('buyer', obj), ['get', 'patch',
                                                               'put'])

    def test_put_pin(self):
        obj = self.create()
        new_pin = self.pin[::-1]  # reverse it so it is different
        res = self.client.put(self.get_detail_url('buyer', obj),
                              data={'uuid': obj.uuid,
                                    'pin': new_pin})
        eq_(res.status_code, 202)
        data = json.loads(res.content)
        eq_(data['pin'], True)
        assert obj.reget().pin.check(new_pin)

    def test_patch_pin(self):
        obj = self.create()
        new_pin = self.pin[::-1]  # reverse it so it is different
        res = self.client.patch(self.get_detail_url('buyer', obj),
                                data={'pin': new_pin})
        eq_(res.status_code, 202)
        assert obj.reget().pin.check(new_pin)

    def test_patch_pin_to_none(self):
        obj = self.create()
        res = self.client.patch(self.get_detail_url('buyer', obj),
                                data={'pin': None})
        eq_(res.status_code, 202)
        assert not obj.reget().pin

    def test_patch_uuid(self):
        obj = self.create()
        res = self.client.patch(self.get_detail_url('buyer', obj),
                                data={'uuid': self.uuid + ':new',
                                      'pin': '1234'})
        eq_(res.status_code, 202)
        eq_(obj.reget().uuid, self.uuid + ':new')

    def test_patch_same_uuid(self):
        obj = self.create()
        res = self.client.patch(self.get_detail_url('buyer', obj),
                                data={'uuid': self.uuid,
                                      'pin': '1234'})
        eq_(res.status_code, 202)
        eq_(obj.reget().uuid, self.uuid)

    def test_paranoid_pin(self):
        mthd = mock.Mock()
        mthd.__name__ = 'mock_signal'
        warning.connect(mthd, weak=False)
        self.client.post(self.list_url, data={'uuid': self.uuid,
                                              'pin': self.pin,
                                              'foo': 'something naughty'})
        assert mthd.called


class TestBuyerPaypal(APITest):

    def setUp(self):
        self.api_name = 'paypal'
        self.uuid = 'sample:uid'
        self.buyer = Buyer.objects.create(uuid=self.uuid)
        self.list_url = self.get_list_url('buyer')

    def test_post(self):
        res = self.client.post(self.list_url,
                               data={'buyer':
                                     '/paypal/buyer/%s/' % self.buyer.pk})
        eq_(res.status_code, 201)
        eq_(BuyerPaypal.objects.count(), 1)

    def test_get(self):
        obj = self.create()
        url = self.get_detail_url('buyer', obj)
        res = self.client.get(url)
        eq_(res.status_code, 200)
        eq_(json.loads(res.content)['key'], False)

    def test_get_generic(self):
        self.create()
        url = self.get_detail_url('buyer', self.buyer, api_name='generic')
        res = self.client.get(url)
        eq_(res.status_code, 200)
        eq_(json.loads(res.content)['paypal']['key'], False)

    def create(self):
        return BuyerPaypal.objects.create(buyer=self.buyer)

    def test_boolean_key(self):
        obj = self.create()
        url = self.get_detail_url('buyer', obj)

        res = self.client.get(url, data={'uuid': self.uuid})
        eq_(json.loads(res.content)['key'], False)

        obj.key = 'abc'
        obj.save()

        res = self.client.get(url, data={'uuid': self.uuid})
        eq_(json.loads(res.content)['key'], True)

    def test_list_allowed(self):
        obj = self.create()
        url = self.get_detail_url('buyer', obj)

        self.allowed_verbs(self.list_url, ['post'])
        self.allowed_verbs(url, ['get', 'delete', 'patch'])

    def test_delete(self):
        obj = self.create()
        url = self.get_detail_url('buyer', obj)
        res = self.client.delete(url, data={'uuid': self.uuid})
        eq_(res.status_code, 204)
        eq_(BuyerPaypal.objects.count(), 0)

    def test_patch(self):
        obj = self.create()
        obj.key = 'foofy'
        obj.save()
        url = self.get_detail_url('buyer', obj)
        res = self.client.patch(url, data={'currency': 'BRL'})
        eq_(res.status_code, 202)
        res = BuyerPaypal.objects.all()
        eq_(res.count(), 1)
        eq_(res[0].currency, 'BRL')
        eq_(res[0].key, 'foofy')  # Ensure key hasn't changed.

    def test_patch_key(self):
        obj = self.create()
        url = self.get_detail_url('buyer', obj)
        obj.key = 'foobar'
        obj.save()
        self.client.patch(url, data={'key': ''})
        eq_(BuyerPaypal.objects.get(pk=obj.pk).key, None)


class TestBuyerVerifyPin(APITest):

    def setUp(self):
        self.api_name = 'generic'
        self.uuid = 'sample:uid'
        self.pin = '1234'
        self.buyer = Buyer.objects.create(uuid=self.uuid, pin=self.pin,
                                          pin_confirmed=True)
        self.list_url = self.get_list_url('verify_pin')

    def test_good_uuid_and_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert data['valid']
        eq_(data['uuid'], self.uuid)

    def test_good_uuid_and_bad_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin[::-1]})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert not data['valid']
        eq_(data['uuid'], self.uuid)

    def test_failure_counted(self):
        self.client.post(self.list_url, data={'uuid': self.uuid,
                                              'pin': self.pin[::-1]})
        eq_(self.buyer.reget().pin_failures, 1)

    @mock.patch.object(settings, 'PIN_FAILURES', 1)
    @mock.patch('solitude.base.log_cef')
    def test_locked_out(self, log_cef):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin[::-1]})
        assert self.buyer.reget().locked_out
        assert log_cef.called
        data = json.loads(res.content)
        assert not data.get('valid')
        assert data.get('locked')

    @mock.patch('solitude.base.log_cef')
    def test_good_pin_but_locked_out(self, log_cef):
        self.buyer.pin_locked_out = datetime.now()
        self.buyer.save()

        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        assert log_cef.called
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert not data.get('valid')
        assert data.get('locked')

    def test_locked_out_over_time(self):
        self.buyer.pin_locked_out = (datetime.now() - timedelta(
            seconds=settings.PIN_FAILURE_LENGTH + 60))
        self.buyer.save()

        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert data['valid']
        assert not data['locked']

    def test_good_reset_failures(self):
        self.buyer.pin_failures = 1
        self.buyer.save()

        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        eq_(self.buyer.reget().pin_failures, 0)

    def test_good_uuid_and_good_pin_and_bad_confirmed(self):
        self.buyer.pin_confirmed = False
        self.buyer.save()
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert not data['valid']
        eq_(data['uuid'], self.uuid)

    def test_bad_uuid(self):
        res = self.client.post(self.list_url, data={'uuid': 'bad:uuid',
                                                    'pin': self.pin})
        eq_(res.status_code, 404)

    def test_empty_post(self):
        res = self.client.post(self.list_url, data={})
        eq_(res.status_code, 400)


class TestBuyerConfirmPin(APITest):

    def setUp(self):
        self.api_name = 'generic'
        self.uuid = 'sample:uid'
        self.pin = '1234'
        self.buyer = Buyer.objects.create(uuid=self.uuid, pin=self.pin)
        self.list_url = self.get_list_url('confirm_pin')

    def test_good_uuid_and_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert data['confirmed']
        assert self.buyer.reget().pin_confirmed
        eq_(data['uuid'], self.uuid)

    def test_good_uuid_and_bad_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': '4321'})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert not data['confirmed']
        assert not self.buyer.reget().pin_confirmed
        eq_(data['uuid'], self.uuid)

    def test_bad_uuid(self):
        res = self.client.post(self.list_url, data={'uuid': 'bad:uuid',
                                                    'pin': '4321'})
        eq_(res.status_code, 404)

    def test_empty_post(self):
        res = self.client.post(self.list_url, data={})
        eq_(res.status_code, 400)


class TestBuyerResetPin(APITest):

    def setUp(self):
        self.api_name = 'generic'
        self.uuid = 'sample:uid'
        self.pin = '1234'
        self.new_pin = '4321'
        self.buyer = Buyer.objects.create(uuid=self.uuid, pin=self.pin,
                                          new_pin=self.new_pin,
                                          needs_pin_reset=True)
        self.list_url = self.get_list_url('reset_confirm_pin')

    def test_good_uuid_and_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.new_pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert data.get('confirmed', False)
        buyer = self.buyer.reget()
        assert not buyer.needs_pin_reset
        assert buyer.pin_confirmed
        eq_(buyer.pin, self.new_pin)
        eq_(data['uuid'], self.uuid)

    def test_good_uuid_and_bad_pin(self):
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        data = json.loads(res.content)
        assert not data.get('confirmed', False)
        buyer = self.buyer.reget()
        assert not buyer.pin == self.new_pin
        assert buyer.needs_pin_reset
        eq_(data['uuid'], self.uuid)

    @mock.patch('solitude.base.log_cef')
    def test_locked_out_reset(self, log_cef):
        self.buyer.pin_failures = 5
        lock_out_time = datetime.today().replace(microsecond=0)
        self.buyer.pin_locked_out = lock_out_time
        self.buyer.save()
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.new_pin})
        eq_(res.status_code, 201)
        assert log_cef.called
        buyer = self.buyer.reget()
        eq_(buyer.pin_failures, 5)
        eq_(buyer.pin_locked_out, lock_out_time)

    def test_locked_out_not_reset(self):
        self.buyer.pin_failures = 5
        self.buyer.save()
        res = self.client.post(self.list_url, data={'uuid': self.uuid,
                                                    'pin': self.pin})
        eq_(res.status_code, 201)
        buyer = self.buyer.reget()
        eq_(buyer.pin_failures, 5)

    def test_bad_uuid(self):
        res = self.client.post(self.list_url, data={'uuid': 'bad:uuid',
                                                    'pin': '4321'})
        eq_(res.status_code, 404)

    def test_empty_post(self):
        res = self.client.post(self.list_url, data={})
        eq_(res.status_code, 400)
