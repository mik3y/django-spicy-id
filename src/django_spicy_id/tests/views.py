from django.http import HttpResponse


def receive_id_and_serve_200(request, id):
    """Dummy view for testing.

    This view tests the `get_url_converter()` functionality, so all it
    has to do is serve a 200 (meaning URL resolution worked). When URL
    resolution fails, this view won't be reached and the unittest will
    receive a 404.
    """
    response_body = id
    return HttpResponse(response_body)
