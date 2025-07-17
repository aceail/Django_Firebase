# reviews/models.py

from django.db import models
from django.contrib.auth.models import User

# 전체 추론 세션을 저장하는 모델
class Inference(models.Model):
    requester = models.ForeignKey(User, on_delete=models.CASCADE)
    system_prompt = models.TextField(blank=True)
    parameters = models.JSONField(default=dict)
    gemini_result = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inference by {self.requester.username} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

# 멀티모달 입력을 순서대로 저장하는 모델
class Input(models.Model):
    inference = models.ForeignKey(Inference, related_name='inputs', on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    input_type = models.CharField(max_length=10) # 'text' or 'image'
    content = models.TextField(blank=True) # 텍스트 내용 또는 이미지 캡션
    image = models.ImageField(upload_to='inference_images/', blank=True, null=True)

    class Meta:
        ordering = ['order'] # 항상 순서대로 정렬

# 각 추론에 대한 평가를 저장하는 모델
class Evaluation(models.Model):
    inference = models.ForeignKey(Inference, on_delete=models.CASCADE)
    evaluator = models.ForeignKey(User, on_delete=models.CASCADE)
    agreement = models.BooleanField()
    quality = models.PositiveIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 한 사용자는 하나의 추론에 대해 한 번만 평가 가능하도록 제약
        unique_together = ('inference', 'evaluator')