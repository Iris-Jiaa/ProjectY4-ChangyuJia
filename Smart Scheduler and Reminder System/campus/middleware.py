class NoCacheAuthenticatedMiddleware:
    """
    Set Cache-Control: no-store on every response served to an authenticated user.

    This prevents the browser back-button from displaying a cached authenticated
    page after the user has logged out — the browser is instructed never to store
    the response in its cache at all.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
