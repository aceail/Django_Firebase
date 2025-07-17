# reviews/views.py

import os
import google.generativeai as genai
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Inference, Input, Evaluation
from PIL import Image

# 로거 설정
logger = logging.getLogger(__name__)

# Google API 키 설정
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY)
except AttributeError:
    logger.error("GOOGLE_API_KEY is not configured in settings.py")
    # 적절한 예외 처리 또는 기본 동작을 여기에 추가할 수 있습니다.
    # 예를 들어, API 기능을 비활성화하거나 에러 페이지를 보여줄 수 있습니다.

@login_required
def inference_page(request):
    """추론 생성 페이지 렌더링"""
    return render(request, "reviews/inference_page.html")

@login_required
def run_inference(request):
    """멀티모달 입력을 받아 추론을 실행하고 결과를 저장"""
    if request.method != "POST":
        return redirect("reviews:inference_page")

    text_prompt = request.POST.get("text_input", "")
    image_parts = []
    
    # 여러 이미지 파일 처리
    if 'image_input' in request.FILES:
        for file in request.FILES.getlist('image_input'):
            try:
                img = Image.open(file)
                image_parts.append(img)
            except Exception as e:
                logger.error(f"Error processing image file {file.name}: {e}")
                # 사용자에게 이미지 파일 오류 알림
                return render(request, "reviews/inference_page.html", {"error": f"이미지 파일 처리 중 오류가 발생했습니다: {file.name}"})

    # 입력값이 모두 없는 경우
    if not text_prompt and not image_parts:
        return render(request, "reviews/inference_page.html", {"error": "텍스트 또는 이미지를 하나 이상 입력해야 합니다."})

    # Inference 객체 생성
    inference = Inference.objects.create(requester=request.user)

    try:
        # 모델 설정 (나중에 선택 가능하도록 확장 가능)
        # 하드코딩된 모델 이름 대신 설정 파일이나 DB에서 가져올 수 있습니다.
        model_name = 'gemini-1.5-pro-latest'
        model = genai.GenerativeModel(model_name)
        
        # API에 전달할 입력 준비
        prompt_parts = [text_prompt] + image_parts
        
        # API 호출
        response = model.generate_content(prompt_parts, stream=False)
        
        # 결과 저장
        inference.response_text = response.text
        inference.model_name = model_name
        inference.is_complete = True
        inference.save()

        # Input 객체 저장
        Input.objects.create(
            inference=inference,
            text_input=text_prompt,
            # 이미지 저장은 필요 시 파일 필드를 모델에 추가하여 구현
        )

        return redirect("reviews:inference_list")

    except genai.types.generation_types.StopCandidateException as e:
        logger.warning(f"Inference stopped for safety reasons: {e} for user {request.user.username}")
        inference.delete() # 실패한 추론 객체 삭제
        return render(request, "reviews/inference_page.html", {"error": "생성된 콘텐츠가 안전하지 않아 요청이 중단되었습니다."})
    except Exception as e:
        logger.error(f"An unexpected error occurred during inference for user {request.user.username}: {e}", exc_info=True)
        inference.delete() # 실패한 추론 객체 삭제
        return render(request, "reviews/inference_page.html", {"error": "알 수 없는 오류가 발생하여 추론에 실패했습니다. 잠시 후 다시 시도해주세요."})


@login_required
def inference_list(request):
    """추론 목록 페이지"""
    inferences = Inference.objects.filter(requester=request.user).order_by("-created_at")
    return render(request, "reviews/inference_list.html", {"inferences": inferences})


@login_required
def evaluation_page(request, inference_id):
    """평가 페이지"""
    inference = get_object_or_404(Inference, pk=inference_id, requester=request.user)
    
    if request.method == "POST":
        score = request.POST.get("score")
        comment = request.POST.get("comment")
        
        Evaluation.objects.create(
            inference=inference, 
            evaluator=request.user, 
            score=score, 
            comment=comment
        )
        return redirect("reviews:inference_list")

    return render(request, "reviews/evaluation_page.html", {"inference": inference})