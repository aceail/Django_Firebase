from django.urls import path
from . import views

app_name = "reviews"

urlpatterns = [
    # 신규 추가: 로그인 후 첫 진입 페이지
    path('', views.root_view, name='root'),

    # 추론 관련 URL
    path('inference/', views.inference_page, name='inference_page'),
    path('inference/run/', views.run_inference, name='run_inference'),

    path('inference/<str:inference_id>/detail/', views.inference_detail, name='inference_detail'),

    # 평가 관련 URL
    path('inferences/', views.inference_list, name='inference_list'),
    path('evaluation/<str:inference_id>/', views.evaluation_page, name='evaluation_page'),
    path('evaluation/<str:inference_id>/submit/', views.submit_evaluation, name='submit_evaluation'),
]
