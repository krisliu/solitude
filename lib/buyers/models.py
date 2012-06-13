from django.db import models


class Buyer(models.Model):
    uuid = models.CharField(max_length=255, db_index=True, unique=True)

    class Meta:
        db_table = 'buyer'


class BuyerPaypal(models.Model):
    # TODO(andym): encrypt these based upon
    # https://bugzilla.mozilla.org/show_bug.cgi?id=763103
    key = models.CharField(max_length=255, blank=True, null=True)
    expiry = models.DateField(blank=True, null=True)
    currency = models.CharField(max_length=3, blank=True, null=True)
    buyer = models.OneToOneField(Buyer, related_name='paypal')

    class Meta:
        db_table = 'buyer_paypal'
