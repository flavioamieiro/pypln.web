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

import datetime
import json

from mimetypes import guess_type

from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext, TemplateDoesNotExist
from django.template.loader import get_template
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.defaultfilters import slugify, pluralize
from django.utils.translation import ugettext as _
from django.utils.translation import ungettext
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse

from core.models import Corpus, Document
from core.forms import CorpusForm, DocumentForm
from django.conf import settings
from apps.core.visualizations import VISUALIZATIONS

from utils import LANGUAGES, create_pipeline
from mongodict import MongoDict


def index(request):
    return render_to_response('core/homepage.html', {},
            context_instance=RequestContext(request))

@login_required
def corpora_list(request, as_json=False):
    if request.method == 'POST':
        form = CorpusForm(request.POST)
        #TODO: do not permit to insert duplicated corpus
        if not form.is_valid():
            request.user.message_set.create(message=_('ERROR: all fields are '
                                                      'required!'))
        else:
            new_corpus = form.save(commit=False)
            new_corpus.slug = slugify(new_corpus.name)
            new_corpus.owner = request.user
            new_corpus.date_created = datetime.datetime.now()
            new_corpus.last_modified = datetime.datetime.now()
            new_corpus.save()
            request.user.message_set.create(message=_('Corpus created '
                                                      'successfully!'))
            return HttpResponseRedirect(reverse('corpora_list'))
    else:
        form = CorpusForm()

    data = {'corpora': Corpus.objects.filter(owner=request.user.id),
            'form': form}
    return render_to_response('core/corpora.html', data,
            context_instance=RequestContext(request))

@login_required
def upload_documents(request, corpus_slug):
    #TODO: accept (and uncompress) .tar.gz and .zip files
    #TODO: enforce document type
    corpus = get_object_or_404(Corpus, slug=corpus_slug, owner=request.user.id)
    form = DocumentForm(request.user, request.POST, request.FILES)
    if form.is_valid():
        docs = form.save(commit=False)
        for doc in docs:
            doc.save()
            # XXX: updating the corpus_set should probably be done in
            # the model, but we'll keep it here since the model might
            # change a bit, and maybe take care of this in a better
            # way.
            doc.corpus_set.add(corpus)
            for corpus in doc.corpus_set.all():
                corpus.last_modified = datetime.datetime.now()
                corpus.save()
            data = {'_id': str(doc.blob.file._id), 'id': doc.id}
            create_pipeline(settings.ROUTER_API, settings.ROUTER_BROADCAST, data,
                            timeout=settings.ROUTER_TIMEOUT)

        number_of_uploaded_docs = len(docs)
        # I know I should be using string.format, but gettext doesn't support
        # it yet: https://savannah.gnu.org/bugs/?30854
        message = ungettext('%(count)s document uploaded successfully!',
                '%(count)s documents uploaded successfully!',
                number_of_uploaded_docs) % {'count': number_of_uploaded_docs}
        messages.info(request, message)
        return HttpResponseRedirect(reverse('corpus_page',
                                            kwargs={'corpus_slug': corpus_slug}))
    else:
        data = {'corpus': corpus, 'form': form}
        return render_to_response('core/corpus.html', data,
                                  context_instance=RequestContext(request))

@login_required
def list_corpus_documents(request, corpus_slug):
    corpus = get_object_or_404(Corpus, slug=corpus_slug, owner=request.user.id)
    form = DocumentForm(request.user)
    data = {'corpus': corpus, 'form': form}
    return render_to_response('core/corpus.html', data,
            context_instance=RequestContext(request))

@login_required
def corpus_page(request, corpus_slug):
    if request.method == 'POST':
        return upload_documents(request, corpus_slug)
    else:
        return list_corpus_documents(request, corpus_slug)

@login_required
def document_page(request, document_slug):
    try:
        document = Document.objects.get(slug=document_slug,
                owner=request.user.id)
    except ObjectDoesNotExist:
        return render_to_response('core/404.html', {},
                context_instance=RequestContext(request))

    data = {'document': document,
            'corpora': Corpus.objects.filter(owner=request.user.id)}
    store = MongoDict(host=settings.MONGODB_CONFIG['host'],
                      port=settings.MONGODB_CONFIG['port'],
                      database=settings.MONGODB_CONFIG['database'],
                      collection=settings.MONGODB_CONFIG['analysis_collection'])
    properties = set(store.get('id:{}:_properties'.format(document.id), []))
    metadata = store.get('id:{}:file_metadata'.format(document.id), {})
    language = store.get('id:{}:language'.format(document.id), None)
    if language is not None:
        metadata['language'] = LANGUAGES[language]
    data['metadata'] = metadata
    visualizations = []
    for key, value in VISUALIZATIONS.items():
        if value['requires'].issubset(properties):
            visualizations.append({'slug': key, 'label': value['label']})
    data['visualizations'] = visualizations
    return render_to_response('core/document.html', data,
        context_instance=RequestContext(request))

@login_required
def document_visualization(request, document_slug, visualization, fmt):
    try:
        document = Document.objects.get(slug=document_slug,
                owner=request.user.id)
    except ObjectDoesNotExist:
        return HttpResponse('Document not found', status=404)

    data = {}
    store = MongoDict(host=settings.MONGODB_CONFIG['host'],
                      port=settings.MONGODB_CONFIG['port'],
                      database=settings.MONGODB_CONFIG['database'],
                      collection=settings.MONGODB_CONFIG['analysis_collection'])

    try:
        properties = set(store['id:{}:_properties'.format(document.id)])
    except KeyError:
        return HttpResponse('Visualization not found', status=404)
    if visualization not in VISUALIZATIONS or \
            not VISUALIZATIONS[visualization]['requires'].issubset(properties):
        return HttpResponse('Visualization not found', status=404)

    data = {}
    for key in VISUALIZATIONS[visualization]['requires']:
        data[key] = store['id:{}:{}'.format(document.id, key)]
    template_name = 'core/visualizations/{}.{}'.format(visualization, fmt)
    try:
        template = get_template(template_name)
    except TemplateDoesNotExist:
        raise Http404("Visualization is not available in this format.")
    if 'process' in VISUALIZATIONS[visualization]:
        data = VISUALIZATIONS[visualization]['process'](data)
    data['document'] = document
    response = render_to_response(template_name, data,
            context_instance=RequestContext(request))
    if fmt != "html":
        response["Content-Type"] = "text/{}; charset=utf-8".format(fmt)
        response["Content-Disposition"] = 'attachment; filename="{}-{}.{}"'.format(document.slug, visualization, fmt)
    return response

@login_required
def document_list(request):
    data = {'documents': Document.objects.filter(owner=request.user.id)}
    return render_to_response('core/documents.html', data,
            context_instance=RequestContext(request))

@login_required
def document_download(request, document_slug):
    try:
        document = Document.objects.get(slug=document_slug,
                owner=request.user.id)
    except ObjectDoesNotExist:
        return render_to_response('core/404.html', {},
                context_instance=RequestContext(request))
    filename = document.blob.name.split('/')[-1]
    file_mime_type = guess_type(filename)[0]
    response = HttpResponse(document.blob, content_type=file_mime_type)
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)
    return response

def search(request, query):
    pass
