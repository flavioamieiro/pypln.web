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

from django.template import RequestContext
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer

class ContextTemplateHTMLRenderer(TemplateHTMLRenderer):
    def resolve_context(self, data, request, response):
        if response.exception:
            data['status_code'] = response.status_code

        return RequestContext(request, {'data': data})

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is not None:
            view = renderer_context['view']
            if hasattr(view, 'object'):
                data['object'] = renderer_context['view'].object

        return super(ContextTemplateHTMLRenderer, self).render(data,
                accepted_media_type, renderer_context)
