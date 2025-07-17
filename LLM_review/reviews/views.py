# reviews/views.py

import os
import google.generativeai as genai
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
def root_view(request):
    """사용자 유형에 따른 초기 리다이렉션"""
    if request.user.is_staff:
        return redirect("inference_page")
    return redirect("inference_list")

@login_required
def inference_page(request):
    """추론 생성 페이지 렌더링"""
    return render(request, "reviews/inference_page.html")

@login_required
def run_inference(request):
    """멀티모달 입력을 받아 추론을 실행하고 결과를 저장"""
    if request.method != "POST" or not request.user.is_staff:
        messages.error(request, "잘못된 접근입니다.")
        return redirect("inference_page")

    system_prompt = request.POST.get("system_prompt", "")
    parameters = {
        "temperature": float(request.POST.get("temperature", 0.7)),
        "top_p": float(request.POST.get("top_p", 1.0)),
        "max_output_tokens": int(request.POST.get("max_output_tokens", 2048)),
    }

    input_items = []
    i = 0
    while f"input_type_{i}" in request.POST:
        input_items.append({
            "order": int(request.POST.get(f"input_order_{i}", i)),
            "type": request.POST.get(f"input_type_{i}"),
            "content": request.POST.get(f"input_content_{i}", ""),
            "file": request.FILES.get(f"input_file_{i}"),
        })
        i += 1

    if not input_items:
        messages.error(request, "텍스트나 이미지를 하나 이상 입력해야 합니다.")
        return redirect("inference_page")

    input_items.sort(key=lambda x: x["order"])

    inference = Inference.objects.create(
        requester=request.user,
        system_prompt=system_prompt,
        parameters=parameters,
        gemini_result="",
    )

    prompt_parts = []
    for item in input_items:
        if item["type"] == "text":
            prompt_parts.append(item["content"])
        elif item["type"] == "image" and item["file"]:
            try:
                img = Image.open(item["file"])
                prompt_parts.append(img)
            except Exception as e:
                logger.error(f"Error processing image file {item['file'].name}: {e}")
                inference.delete()
                messages.error(request, f"이미지 처리 중 오류가 발생했습니다: {item['file'].name}")
                return redirect("inference_page")
            if item["content"]:
                prompt_parts.append(item["content"])

    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        response = model.generate_content(prompt_parts, stream=False)

        inference.gemini_result = response.text
        inference.save()

        for item in input_items:
            Input.objects.create(
                inference=inference,
                order=item["order"],
                input_type=item["type"],
                content=item["content"],
                image=item["file"] if item["type"] == "image" else None,
            )

        messages.success(request, "추론이 완료되었습니다.")
        return redirect("inference_list")

    except genai.types.generation_types.StopCandidateException:
        inference.delete()
        messages.error(request, "생성된 콘텐츠가 안전하지 않아 요청이 중단되었습니다.")
        return redirect("inference_page")
    except Exception as e:
        logger.error(f"Unexpected error during inference for user {request.user.username}: {e}", exc_info=True)
        inference.delete()
        messages.error(request, "알 수 없는 오류가 발생하여 추론에 실패했습니다.")
        return redirect("inference_page")


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


@login_required
def submit_evaluation(request, inference_id):
    """평가 결과 저장 후 상세 페이지로 리다이렉트"""
    inference = get_object_or_404(Inference, pk=inference_id, requester=request.user)

    if request.method == "POST":
        Evaluation.objects.create(
            inference=inference,
            evaluator=request.user,
            score=request.POST.get("score"),
            comment=request.POST.get("comment", ""),
        )

    return redirect("evaluation_page", inference_id=inference.id)
