from datetime import datetime

from django.forms import formset_factory
from django.forms.models import inlineformset_factory
from django.http.response import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, redirect, get_object_or_404
import tempfile
import zipfile
import partridge as ptg
from django.contrib import messages

# Create your views here.
from django.views.generic import ListView, DetailView

from gtfs_grading_app.Functions.functions import get_next_review_item, \
    get_previous_review_item, get_or_none, get_mode_drop_down, list_to_tuple_of_tuples
from gtfs_grading_app.classes.classes import review_widget_factory, consistency_widget_factory, \
    results_capture_widget_factory, ReviewWidget, DataSelector
from gtfs_grading_app.forms import GtfsZipForm, AddReviewCategory, AddReviewWidget, AddConsistencyWidget, \
    AddResultsCaptureWidget, AddResultCaptureScore, AddReviewWidgetRelatedFieldSameTable, ChooseDataSelector, \
    NewReviewForm, ResultForm
from gtfs_grading_app.models import review_category, review_widget, consistency_widget, results_capture_widget, \
    gtfs_field, consistency_widget_visual_example, consistency_widget_link, score, review, result, result_reference, \
    result_image

from gtfs_grading_app.gtfs_spec.import_gtfs_spec import get_cascading_drop_down, get_field_type

# TODO change name
def new_home(request):
    """Home page view"""

    return render(request, 'home.html', {})

def about(request):
    """Home page view"""
    active_page = 'about'
    return render(request, 'about.html', {'active_page':active_page})

def administration(request):
    active_page = 'admin'
    existing_review_categories = review_category.objects.select_related().all()

    return render(request, 'admin/administration.html', {'active_page': active_page,
                                                         'existing_review_categories': existing_review_categories})

def amdin_add_new(request):
    active_page = 'admin'
    active_review = 'add_new'
    drop_down = get_cascading_drop_down()

    existing_review_categories = review_category.objects.select_related().all()

    if request.POST:
        form = AddReviewCategory(request.POST, prefix="form_ReviewCategory")
        if form.is_valid():
            form.save()
            return redirect('admin_details', review_id=review_category.objects.all().order_by("-id")[0].id)
    else:
        form = AddReviewCategory(prefix="form_ReviewCategory")

    return render(request, 'admin/admin_add_new.html', {'active_page': active_page,
                                                        'active_review': active_review,
                                                        'form': form,
                                                        'drop_down': drop_down,
                                                        'existing_review_categories': existing_review_categories})


def admin_details(request, review_id):
    active_page = 'admin'
    existing_review_categories = review_category.objects.select_related().all()
    current_review = review_category.objects.select_related().get(id=review_id)
    active_review = current_review.id

    scores = score.objects.filter(results_capture_widget_id=current_review.results_capture_widget_id).order_by('-score')


    related_fields_same_table = current_review.review_widget.related_field_same_table.all()


    choose_data_selector = ChooseDataSelector(my_review_category=current_review,
                                              prefix="choose_data_selector",
                                              initial={'name': current_review.data_selector.name,
                                                       'number_to_review': current_review.data_selector.number_to_review})

    add_score_form = AddResultCaptureScore(initial={
        'results_capture_widget': current_review.results_capture_widget}, prefix='score_form')
    add_field_same_table_form = AddReviewWidgetRelatedFieldSameTable(my_gtfs_table_name=current_review.gtfs_field.table,
                                                                     prefix="field_same_table_form",
                                                                     initial={'review_widget_id': current_review.review_widget.id})

    update_results_capture_widget = AddResultsCaptureWidget(instance=current_review.results_capture_widget,
                                                            prefix="update_results_capture_widget")


    if request.POST:
        if 'choose_data_selector' in request.POST:
            choose_data_selector = ChooseDataSelector(request.POST,
                                                      my_review_category=current_review,
                                                      prefix="choose_data_selector",
                                                      )
            if choose_data_selector.is_valid():
                choose_data_selector.save()
                choose_data_selector = ChooseDataSelector(my_review_category=current_review,
                                                          prefix="choose_data_selector",
                                                          initial={'name': current_review.data_selector.name,
                                                                   'number_to_review': current_review.data_selector.number_to_review})


        if 'add_new_score' in request.POST:
            add_score_form = AddResultCaptureScore(request.POST, prefix='score_form')
            if add_score_form.is_valid():
                add_score_form.save()
                add_score_form = AddResultCaptureScore(initial={
                    'results_capture_widget': current_review.results_capture_widget}, prefix='score_form')

        if 'add_field_same_table' in request.POST:
            add_field_same_table_form = AddReviewWidgetRelatedFieldSameTable(request.POST,
                                                                             my_gtfs_table_name=current_review.gtfs_field.table,
                                                                             prefix="field_same_table_form",
                                                                             )
            if add_field_same_table_form.is_valid():
                add_field_same_table_form.save()
                add_field_same_table_form = AddReviewWidgetRelatedFieldSameTable(my_gtfs_table_name=current_review.gtfs_field.table,
                                                                                 prefix="field_same_table_form",
                                                                                 initial={'review_widget_id': current_review.review_widget.id})
            else:
                raise ValueError

        if 'update_results_capture_widget' in request.POST:
            update_results_capture_widget = AddResultsCaptureWidget(request.POST,
                                                                    instance=current_review.results_capture_widget,
                                                                    prefix="update_results_capture_widget",
                                                                    )
            if update_results_capture_widget.is_valid():
                update_results_capture_widget.save()
                update_results_capture_widget = AddResultsCaptureWidget(instance=current_review.results_capture_widget,
                                                                        prefix="update_results_capture_widget")

    return render(request, 'admin/admin_details.html', {'active_page': active_page,
                                                        'active_review': active_review,
                                                        'current_review': current_review,
                                                        'existing_review_categories': existing_review_categories,
                                                        'choose_data_selector': choose_data_selector,
                                                        'scores': scores,
                                                        'add_score_form': add_score_form,
                                                        'related_fields_same_table': related_fields_same_table,
                                                        'add_field_same_table_form': add_field_same_table_form,
                                                        'update_results_capture_widget': update_results_capture_widget})


def evaluate_feed(request, review_id=None, active_review_category_id=None, active_result_number=None):
    # TODO reorder to improve performance
    if review_id is None:
        return redirect(start_new_evaluation)
    if active_review_category_id is None:
        active_review_category = review_category.objects.first()
    else:
        active_review_category = get_object_or_404(review_category, pk=active_review_category_id)
    if active_result_number is None:
        active_result_number = 1

    active_review = get_object_or_404(review, pk=review_id)

    # calculate progress
    total_results = result.objects.filter(review_id=review_id).count()
    completed_results = result.objects.filter(review_id=review_id).exclude(score=None).count()
    percentage_complete = int(round(completed_results/total_results, 2) * 100)

    # collect results
    review_categories = review_category.objects.all()
    results = result.objects.filter(review_id=review_id, review_category_id=active_review_category.id)
    active_result = results[active_result_number-1]
    max_items = results.count()

    # get widgets
    active_review_widget = review_widget_factory(active_review_category.review_widget, active_result)
    active_result_capture_widget = results_capture_widget_factory(active_review_category.results_capture_widget, active_result)

    # get next and last item paths
    next_review_path = get_next_review_item(active_result_number,
                                            max_items,
                                            active_review,
                                            active_review_category,
                                            review_categories)
    previous_review_path = get_previous_review_item(active_result_number,
                                                    max_items,
                                                    active_review,
                                                    active_review_category,
                                                    review_categories)

    if request.POST:
        form = active_result_capture_widget.get_form(request.POST, request.FILES)
        if form.is_valid():
            form.__save__()
            if next_review_path is None:
                return redirect('review_evaluation_results', review_id=active_review.id)
            else:
                if active_review.review_status == "In progress":
                    return redirect(next_review_path)
                else:
                    return redirect('review_evaluation_results', active_review.id)

    else:
        reference = get_or_none(result_reference, result_id=active_result.id)
        if reference:
            reference_name = reference.reference_name
            reference_url = reference.url
            reference_published_reference_date = reference.published_reference_date
        else:
            reference_name = None
            reference_url = None
            reference_published_reference_date = None
        image = get_or_none(result_image, result_id=active_result.id)
        if image:
            image = image.image
        else:
            image = None

        form = active_result_capture_widget.get_form(initial={'result_id': active_result.id,
                                                              'review_category_id': active_result.review_category_id,
                                                              'score_id': active_result.score_id,
                                                              'score_reason': active_result.score_reason,
                                                              'reference_name': reference_name,
                                                              'reference_url': reference_url,
                                                              'published_reference_date': reference_published_reference_date,
                                                              'image': image
                                                              })

    review_widget_template = active_review_widget.get_template()
    review_widget_context = active_review_widget.get_template_context()
    result_capture_template = active_result_capture_widget.get_template()
    result_capture_context = active_result_capture_widget.get_template_context()

    context = {'active_review': active_review,
               'review_categories': review_categories,
               'active_review_category': active_review_category,
               'active_result': active_result,
               'active_result_number': active_result_number,
               'max_items': max_items,
               'review_widget_template': review_widget_template,
               'result_capture_template': result_capture_template,
               'form': form,
               'next_review_path': next_review_path,
               'previous_review_path': previous_review_path,
               'percentage_complete': percentage_complete}

    context.update(review_widget_context)
    context.update(result_capture_context)

    return render(request, 'evaluate_feed.html', context)


def evaluate_feed_by_result_id(request, review_id, active_review_category_id, active_result_id):
    results = result.objects.filter(review_id=review_id, review_category_id=active_review_category_id)
    active_result = result.objects.get(id=active_result_id)
    print('test')
    i = 0
    for my_result in results:
        if my_result == active_result:
            return redirect('evaluate_feed', review_id, active_review_category_id, i)
        else:
            i += 1

    raise Http404("Review not found")

def review_evaluation_results(request, review_id, active_result_id=None):
    review_categories = review_category.objects.all()
    active_review = get_object_or_404(review, pk=review_id)
    print(active_review.review_status)
    if active_review.review_status == "In progress":
        print('true')
        active_review.mark_status_in_review()
    results = result.objects.filter(review_id=active_review.id).select_related()

    context = {'active_review': active_review,
               'review_categories': review_categories,
               'results': results}

    if active_result_id:
        active_result = result.objects.get(id=active_result_id)
        active_review_widget = active_result.review_category.review_widget
        my_review_widget = review_widget_factory(active_review_widget, active_result)
        review_widget_template = my_review_widget.get_template()
        review_widget_context = my_review_widget.get_template_context()

        image = get_or_none(result_image, result_id=active_result.id)
        if image:
            image = image.image

        context.update({'active_result': active_result,
                        'review_widget_template': review_widget_template,
                        'image': image})
        context.update(review_widget_context)

    return render(request, 'review_evaluation_results.html', context)


def mark_review_complete(request, review_id):
    active_review = get_object_or_404(review, id=review_id)
    active_review.review_status = 'Completed'
    active_review.completed_date = datetime.now()
    active_review.save()
    messages.success(request, "Your review has been marked complete.")

    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def view_completed_review(request, review_id, active_result_id=None):
    active_page = 'search'
    review_categories = review_category.objects.all()
    active_review = get_object_or_404(review, pk=review_id)
    results = result.objects.filter(review_id=active_review.id).select_related()

    context = {'active_page': active_page,
               'active_review': active_review,
               'review_categories': review_categories,
               'results': results}

    if active_result_id:
        active_result = result.objects.get(id=active_result_id)
        active_review_widget = active_result.review_category.review_widget
        my_review_widget = review_widget_factory(active_review_widget, active_result)
        review_widget_template = my_review_widget.get_template()
        review_widget_context = my_review_widget.get_template_context()

        image = get_or_none(result_image, result_id=active_result.id)
        if image:
            image = image.image

        context.update({'active_result': active_result,
                        'review_widget_template': review_widget_template,
                        'image': image})
        context.update(review_widget_context)

    return render(request, "view_completed_review.html", context)



def start_new_evaluation(request):
    active_page = 'evaluate'
    if request.session.get('gtfs_feed', None):
        tmp_dir = request.session['gtfs_feed']
        gtfs_feed = ptg.load_feed(tmp_dir)
        agency_options = gtfs_feed.agency['agency_name'].tolist()
        agency_options = list_to_tuple_of_tuples(agency_options)
        mode_options = list(set(gtfs_feed.routes['route_type'].tolist()))
        mode_options = get_mode_drop_down(mode_options)
        my_new_review_form = NewReviewForm(agency_options=agency_options, mode_options=mode_options)
    else:
        my_new_review_form = None
    if request.POST:
        my_new_review_form = NewReviewForm(request.POST, agency_options=agency_options, mode_options=mode_options)
        if my_new_review_form.is_valid():
            agency_name = my_new_review_form.cleaned_data['agency']
            mode = my_new_review_form.cleaned_data['mode']
            new_session_gtfs_path, my_review = DataSelector.setup_initial_data_for_review(request.session['gtfs_feed'],
                                                                                          agency_name,
                                                                                          mode)
            request.session['gtfs_feed'] = new_session_gtfs_path
            return redirect(evaluate_feed, review_id=my_review.id)

    return render(request, 'start_new_evaluation.html', {'active_page': active_page,
                                                         'my_new_review_form': my_new_review_form})

def search_competed_review(request):
    active_page = 'search'
    completed_reviews = review.objects.filter(review_status="Completed")

    return render(request, 'search_completed_review.html', {'active_page': active_page,
                                                           'completed_reviews': completed_reviews})


def home(request):
    """Home page view"""
    form = GtfsZipForm()
    if 'gtfs_feed' in request.session:
        print('GTFS Feed present: ' + request.session['gtfs_feed'])

    else:
        print('no session')

    return render(request, 'file_upload.html', {'form': form})


def post_gtfs_zip(request):
    """This view is a post request for saving GTFS zip files to a temp folder for use latter"""
    if not request.method == 'POST' or not request.FILES:
        return HttpResponse('You must submit a .zip file', status=400)
    else:
        form = GtfsZipForm(request.POST, request.FILES)
        if form.is_valid():

            try:
                # TODO implement better file management
                tmp_dir = tempfile.mkdtemp()
                zip_ref = zipfile.ZipFile(request.FILES['file'], 'r')
                zip_ref.extractall(tmp_dir)
                gtfs_feed = ptg.load_feed(tmp_dir)
                request.session['gtfs_feed'] = tmp_dir
                messages.success(request, "Your GTFS file has been successfully uploaded and parsed!")
            except:
                messages.error(request,
                               'There was an error uploading your GTFS feed.  Please be sure you submitted a valid .zip GTFS file and try again.')
        else:
            messages.error(request,
                           'There was an error uploading your GTFS feed.  Please be sure you submitted a valid .zip GTFS file and try again.')

        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def gtfs_admin(request):
    """admin page for adding new review categories (and potentially other features down the road)"""

    return render(request, 'admin/gtfs_admin.html')


class ViewReviewCategory(ListView):
    """List view of review categories"""
    template_name = 'admin/view_review_category.html'
    queryset = review_category.objects.select_related()
    context_object_name = 'review_category'


class ViewReviewWidget(DetailView):

    def get(self, request, *args, **kwargs):
        this_review_widget = get_object_or_404(review_widget, pk=kwargs['pk'])
        context = {'review_widget': this_review_widget}
        return render(request, 'admin/view_review_widget.html', context)

#
# def add_review_category(request):
#     if request.method == 'POST':
#         updated_data = request.POST.copy()
#
#         gtfs_type = get_field_type(request.POST.get('form_ReviewCategory-gtfs_field'), request.POST.get('form_ReviewCategory-review_table'))
#
#         obj, created = gtfs_field.objects.get_or_create(name=request.POST.get('form_ReviewCategory-gtfs_field'),
#                                                         table=request.POST.get('form_ReviewCategory-review_table'),
#                                                         type=gtfs_type)
#
#         updated_data.update({'form_ReviewCategory-gtfs_field': obj})
#
#         form_ReviewCategory = AddReviewCategory(updated_data, prefix="form_ReviewCategory")
#         form_ReviewWidget = AddReviewWidget(request.POST, prefix="form_ReviewWidget")
#         form_AddConsistencyWidget = AddConsistencyWidget(request.POST, prefix="form_AddConsistencyWidget")
#         form_AddResultsCaptureWidget = AddResultsCaptureWidget(request.POST, prefix="form_AddResultsCaptureWidget")
#
#         if form_ReviewCategory.is_valid() and form_ReviewWidget.is_valid() and \
#                 form_AddConsistencyWidget.is_valid() and form_AddResultsCaptureWidget.is_valid():
#             this_review_widget = form_ReviewWidget.save()
#             this_consistency_widget = form_AddConsistencyWidget.save()
#             this_results_capture_widget = form_AddResultsCaptureWidget.save()
#
#             this_review_category = form_ReviewCategory.save(commit=False)
#             this_review_category.review_widget = this_review_widget
#             this_review_category.consistency_widget = this_consistency_widget
#             this_review_category.results_capture_widget = this_results_capture_widget
#
#             this_review_category.save()
#
#             return redirect('configure_widget', widget_type="review", widget_id=this_review_widget.id)
#
#     else:
#         from gtfs_grading_app.gtfs_spec.import_gtfs_spec import get_gtfs_table_tuple
#         t = get_gtfs_table_tuple()
#         form_ReviewCategory = AddReviewCategory(prefix="form_ReviewCategory")
#         form_ReviewWidget = AddReviewWidget(prefix="form_ReviewWidget")
#         form_AddConsistencyWidget = AddConsistencyWidget(prefix="form_AddConsistencyWidget")
#         form_AddResultsCaptureWidget = AddResultsCaptureWidget(prefix="form_AddResultsCaptureWidget")
#
#     drop_down = get_cascading_drop_down()
#
#     return render(request, 'admin/add_review_category.html', {'form_ReviewCategory': form_ReviewCategory,
#                                                               'form_ReviewWidget': form_ReviewWidget,
#                                                               'form_AddConsistencyWidget': form_AddConsistencyWidget,
#                                                               'form_AddResultsCaptureWidget': form_AddResultsCaptureWidget,
#                                                               'drop_down': drop_down})


def delete_review_category(request, review_category_id):
    instance = review_category.objects.get(id=review_category_id)
    instance.delete()
    messages.success(request, 'The review category has been deleted')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

#
# def configure_widget(request, widget_type, widget_id):
#     if widget_type == "review":
#         this_widget = review_widget_factory(get_object_or_404(review_widget, id=widget_id))
#     elif widget_type == "consistency":
#         this_widget = consistency_widget_factory(get_object_or_404(consistency_widget, id=widget_id))
#     elif widget_type == "results_capture":
#         this_widget = results_capture_widget_factory(get_object_or_404(results_capture_widget, id=widget_id))
#     else:
#         raise NotImplementedError
#
#     creation_form = this_widget.get_creation_form(instance=this_widget.model_instance)
#
#     if request.POST:
#         forms = this_widget.get_configuration_form(request.POST, request.FILES)
#
#         any_valid = False
#         for key, value in forms.items():
#             if value[0].is_valid():
#                 all_valid = True
#                 value[0].save()
#                 return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
#
#     else:
#         forms = this_widget.get_configuration_form()
#
#     template = this_widget.get_configuration_template()
#
#     if not template:
#         template = 'admin/configure_widget.html'
#
#     return render(request, template, {'forms': forms,
#                                       'this_widget': this_widget,
#                                       'creation_form': creation_form
#                                       })


def delete_consistency_widget_visual_example(request, image_id):
    image = get_object_or_404(consistency_widget_visual_example, id=image_id)
    image.delete()
    messages.success(request, 'The image has been deleted')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def delete_consistency_widget_link(request, link_id):
    image = get_object_or_404(consistency_widget_link, id=link_id)
    image.delete()
    messages.success(request, 'The link has been deleted')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def delete_review_widget_related_field_same_table(request, widget_id, field_id):
    widget = get_object_or_404(review_widget, id=widget_id)
    field = get_object_or_404(gtfs_field, id=field_id)
    widget.related_field_same_table.remove(field)
    messages.success(request, 'The related field has been removed')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def delete_results_capture_score(request, score_id):
    my_score = score.objects.get(id=score_id)
    my_score.delete()
    messages.success(request, 'The score has been deleted')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def skip_it_replace_result(request, result_id):
    if not request.session['gtfs_feed']:
        messages.error("You do not have an active GTFS feed.  You may not skip any fields in this review.")




    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
