# reviews/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpRequest
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
import google.generativeai as genai

# 새로 만든 모델들을 import 합니다.
from .models import Inference, Input, Evaluation

# 역할 기반 리다이렉트 뷰
@login_required
def root_view(request: HttpRequest):
    if request.user.is_staff:
        return redirect('inference_page')
    else:
        return redirect('inference_list')

# API 키 설정
GOOGLE_API_KEY = getattr(settings, 'GOOGLE_API_KEY', None)
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

# 추론 페이지 뷰
@login_required
def inference_page(request: HttpRequest):
    if not request.user.is_staff:
        return redirect('root')
    return render(request, 'reviews/inference_page.html')

# 추론 실행 뷰
@login_required
@transaction.atomic # 여러 DB 작업을 하나의 트랜잭션으로 묶어 안정성 확보
def run_inference(request: HttpRequest):
    if not request.user.is_staff or request.method != 'POST':
        return redirect('inference_page')

    try:
        # 1. Gemini API 호출 준비
        system_prompt = request.POST.get('system_prompt', '')
        parameters = {
            'temperature': float(request.POST.get('temperature', 0.7)),
            'top_p': float(request.POST.get('top_p', 1.0)),
            'max_output_tokens': int(request.POST.get('max_output_tokens', 2048)),
        }
        gemini_contents = []
        
        # 2. Inference 객체 먼저 생성
        inference = Inference.objects.create(
            requester=request.user,
            system_prompt=system_prompt,
            parameters=parameters,
            gemini_result="" # 결과는 나중에 채움
        )

        # 3. 멀티모달 입력 처리
        input_items = []
        i = 0
        while True:
            if f'input_type_{i}' not in request.POST: break
            input_items.append({
                'order': int(request.POST.get(f'input_order_{i}')),
                'type': request.POST.get(f'input_type_{i}'),
                'content': request.POST.get(f'input_content_{i}'),
                'file': request.FILES.get(f'input_file_{i}')
            })
            i += 1
        
        input_items.sort(key=lambda x: x['order'])

        for item in input_items:
            # DB에 Input 객체 생성
            input_obj = Input.objects.create(
                inference=inference,
                order=item['order'],
                input_type=item['type'],
                content=item['content'],
                image=item['file'] if item['type'] == 'image' else None
            )
            
            # Gemini API 요청 데이터 구성
            if item['type'] == 'text':
                gemini_contents.append({'text': item['content']})
            elif item['type'] == 'image' and item['file']:
                image_file = item['file']
                image_file.seek(0)
                image_part = {'mime_type': image_file.content_type, 'data': image_file.read()}
                gemini_contents.append({'image': image_part})
                if item['content']:
                    gemini_contents.append({'text': item['content']})
        
        # 4. Gemini API 호출
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(
            contents=gemini_contents,
            generation_config=genai.types.GenerationConfig(**parameters),
            system_instruction=system_prompt
        )

        # 5. API 결과를 Inference 객체에 업데이트
        inference.gemini_result = response.text
        inference.save()
        
        return redirect('evaluation_page', inference_id=inference.id)

    except Exception as e:
        print(f"An error occurred: {e}")
        # 오류 발생 시 생성했던 빈 Inference 객체 삭제
        if 'inference' in locals() and inference.pk:
            inference.delete()
        return redirect('inference_page')

# 평가 목록 뷰
@login_required
def inference_list(request: HttpRequest):
    inferences = Inference.objects.all().order_by('-created_at')
    context = {'inferences': inferences}
    return render(request, 'reviews/inference_list.html', context)

# 평가 상세 페이지 뷰
@login_required
def evaluation_page(request: HttpRequest, inference_id: int):
    inference = get_object_or_404(Inference, pk=inference_id)
    evaluations = Evaluation.objects.filter(inference=inference)
    
    user_has_evaluated = evaluations.filter(evaluator=request.user).exists()
    
    eval_count = evaluations.count()
    agreement_count = evaluations.filter(agreement=True).count()
    
    # 평가가 있을 경우에만 평균 계산
    total_quality = sum(e.quality for e in evaluations)
    avg_quality = (total_quality / eval_count) if eval_count > 0 else 0
    
    context = {
        'inference': inference,
        'user_has_evaluated': user_has_evaluated,
        'eval_count': eval_count,
        'avg_quality': round(avg_quality, 2),
        'agreement_rate': int((agreement_count / eval_count) * 100) if eval_count > 0 else 0,
    }
    return render(request, 'reviews/evaluation_page.html', context)

# 평가 제출 뷰
@login_required
def submit_evaluation(request: HttpRequest, inference_id: int):
    inference = get_object_or_404(Inference, pk=inference_id)
    if request.method == 'POST' and not request.user.is_staff:
        # 중복 평가 방지
        if not Evaluation.objects.filter(inference=inference, evaluator=request.user).exists():
            Evaluation.objects.create(
                inference=inference,
                evaluator=request.user,
                agreement=request.POST.get('agreement') == 'true',
                quality=int(request.POST.get('quality')),
                comment=request.POST.get('comment', ''),
            )
    return redirect('evaluation_page', inference_id=inference.id)
