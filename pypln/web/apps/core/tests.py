"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from django.core.urlresolvers import reverse
from django.conf import settings


class CorpusViewTest(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse('corpus_page',
            kwargs={'corpus_slug': 'test-corpus'}))
        self.assertEqual(response.status_code, 302)
        login_url = settings.LOGIN_URL
        self.assertTrue(login_url in response['Location'])
