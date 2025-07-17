# LLM_review/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings # settings import 추가
from django.conf.urls.static import static # static import 추가

urlpatterns = [
    path('', include('reviews.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]

# 개발 환경에서 사용자가 업로드한 미디어 파일을 서빙하기 위한 설정
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)