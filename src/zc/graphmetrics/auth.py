import bobo
import re

authorized = re.compile(r'@(zope|reachtapp)\.com$').search
def checker(self, request, func):
    if not authorized(request.remote_user):
        return bobo.redirect(
            '/persona/login.html?came_from='+request.path_info)

def who(request):
    return request.remote_user.split('@')[0]
