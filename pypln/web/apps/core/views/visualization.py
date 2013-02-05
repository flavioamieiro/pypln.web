# coding: utf-8
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
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic.base import TemplateView

from mongodict import MongoDict

from apps.core.models import Document
from apps.core.visualizations import pos_highlighter

class VisualizationView(TemplateView):
    """
    Base class for visualization views.
    Each visualization should extend this, declare it's requirements, base
    template name, and a process method that returns the data necessary in the
    template context.
    """
    requires = set()
    base_template_name = 'core/visualizations/'

    @property
    def template_name(self):
        return '{}.{}'.format(self.base_template_name, self.kwargs['fmt'])

    # Seriously? Do we really need this?
    # https://docs.djangoproject.com/en/dev/topics/class-based-views/#decorating-the-class
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(VisualizationView, self).dispatch(*args, **kwargs)

    def get_data_from_store(self):
        store = MongoDict(host=settings.MONGODB_CONFIG['host'],
                          port=settings.MONGODB_CONFIG['port'],
                          database=settings.MONGODB_CONFIG['database'],
                          collection=settings.MONGODB_CONFIG['analysis_collection'])

        try:
            properties = set(store['id:{}:_properties'.format(self.document.id)])
        except KeyError:
            # FIXME: We know that we need better information about pipeline
            # status. https://github.com/NAMD/pypln.web/issues/46
            raise Http404("Visualization not found for this document.")

        if not self.requires.issubset(properties):
            # FIXME: We know that we need better information about pipeline
            # status. https://github.com/NAMD/pypln.web/issues/46
            raise Http404("Visualization not ready for this document. "
                    "This means that the necessary processing is not finished "
                    "or that an error has occured.")

        data = {}
        for key in self.requires:
            data[key] = store['id:{}:{}'.format(self.document.id, key)]

        return data

    def process(self):
        raise NotImplementedError

    def get_context_data(self, document_slug, fmt):
        self.document = get_object_or_404(Document, slug=document_slug,
                    owner=self.request.user.id)

        context = self.process()
        context['document'] = self.document
        return context

class PosHighlighterVisualization(VisualizationView):
    requires = set(['pos', 'tokens'])
    base_template_name = 'core/visualizations/pos-highlighter'

    def process(self):
        input_data = self.get_data_from_store()
        return pos_highlighter(input_data)

    def render_to_response(self, context, **response_kwargs):
        response = super(PosHighlighterVisualization, self).render_to_response(
                context, **response_kwargs)

        fmt = self.kwargs['fmt']
        if fmt != "html":
            response["Content-Type"] = "text/{}; charset=utf-8".format(fmt)
            response["Content-Disposition"] = ('attachment; '
                    'filename="{}-part-of-speech.{}"').format(self.document.slug, fmt)
        return response