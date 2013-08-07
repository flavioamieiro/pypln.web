# -*- coding:utf-8 -*-
#
# Copyright 2012 NAMD-EMAP-FGV
#
# This file is part of PyPLN. You can get more information at: http://pypln.org/.
#
# PyPLN is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PyPLN is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PyPLN.  If not, see <http://www.gnu.org/licenses/>.

from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase


class ChangePasswordTestCase(TestCase):
    fixtures = ['users']

    def test_requires_login(self):
        response = self.client.get(reverse('change-password'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response['Location'])

    def test_page_is_rendered_correctly(self):
        self.client.login(username="user", password="user")
        response = self.client.get(reverse('change-password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "user/change_password.html")
        self.assertNotIn(settings.TEMPLATE_STRING_IF_INVALID, response.content)

    def test_form_is_in_context(self):
        self.client.login(username="user", password="user")
        response = self.client.get(reverse('change-password'))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIsInstance(response.context["form"], PasswordChangeForm)

    def test_cant_change_if_provides_wrong_old_password(self):
        self.client.login(username="user", password="user")
        response = self.client.post(reverse('change-password'), {
            "old_password": "wrongpasswd",
            "new_password1": "newpassword",
            "new_password2": "newpassword"})
        form_errors = response.context["form"].errors
        self.assertIn("old_password", form_errors)

    def test_cant_change_if_provided_passwords_dont_match(self):
        self.client.login(username="user", password="user")
        response = self.client.post(reverse('change-password'), {
            "old_password": "user",
            "new_password1": "newpassword",
            "new_password2": "doesnotmatch"})
        form_errors = response.context["form"].errors
        self.assertIn("new_password2", form_errors)

    def test_password_is_changed_successfuly(self):
        self.client.login(username="user", password="user")
        response = self.client.post(reverse('change-password'), {
            "old_password": "user",
            "new_password1": "newpassword",
            "new_password2": "newpassword"})

        self.assertTrue(response.context["messages"].added_new)
        user = User.objects.get(username="user")
        self.assertFalse(user.check_password("user"))
        self.assertTrue(user.check_password("newpassword"))
