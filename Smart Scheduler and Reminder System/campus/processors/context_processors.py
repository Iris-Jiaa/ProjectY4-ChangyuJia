from campus.models import Notification

def user_notifications(request):
    """
    This function provides notification-related context to all templates.
    """
    if request.user.is_authenticated:
        if request.user.username == 'Jia':
            return {
                'unread_notifications': [],
                'unread_notifications_count': 0,
                'all_notifications': [],
            }

        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False)
        all_notifications = Notification.objects.filter(recipient=request.user)
        context = {
            'unread_notifications': unread_notifications,
            'unread_notifications_count': unread_notifications.count(),
            'all_notifications': all_notifications,
        }
    else:
        context = {
            'unread_notifications': [],
            'unread_notifications_count': 0,
            'all_notifications': [],
        }
    return context