#!/usr/bin/env python3
"""
회원 데이터를 Google Sheets로 수동 동기화하는 스크립트
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.sheets_sync import SheetsSync
from app.services.local_cache import LocalCache


def sync_member_to_sheets(member_id: str):
    """특정 회원의 데이터를 Google Sheets에 업로드"""
    
    # credentials 경로
    creds_path = project_root / 'config' / 'credentials.json'
    
    if not creds_path.exists():
        print(f"❌ credentials.json 파일을 찾을 수 없습니다: {creds_path}")
        return False
    
    try:
        # LocalCache 초기화
        print("[1/4] LocalCache 초기화...")
        local_cache = LocalCache()
        
        # 회원 정보 조회
        member = local_cache.get_member(member_id)
        if not member:
            print(f"❌ 회원 {member_id}를 로컬 DB에서 찾을 수 없습니다.")
            return False
        
        print(f"✓ 회원 정보: {member['name']} ({member_id})")
        
        # SheetsSync 초기화
        print("[2/4] Google Sheets 연결...")
        sheets_sync = SheetsSync(credentials_path=str(creds_path))
        if not sheets_sync.connect():
            print("❌ Google Sheets 연결 실패")
            return False
        
        # 회원 데이터를 Sheets에 업로드
        print("[3/4] 회원 데이터를 Sheets에 업로드...")
        
        # members 시트에 데이터 추가/업데이트
        members_data = [[
            member_id,
            member.get('name', ''),
            member.get('phone', ''),
            member.get('status', 'active'),
            member.get('payment_password', ''),
        ]]
        
        # members 시트 가져오기 및 기존 회원 확인
        members_sheet = sheets_sync.spreadsheet.worksheet('members')
        existing_records = members_sheet.get_all_records()
        existing_ids = [str(m['member_id']) for m in existing_records]
        
        if member_id in existing_ids:
            # 업데이트
            row_idx = existing_ids.index(member_id) + 2  # 헤더 제외 (+1), 0-based to 1-based (+1)
            members_sheet.update(f'A{row_idx}:E{row_idx}', members_data)
            print(f"✓ 회원 {member_id} 업데이트 완료 (행 {row_idx})")
        else:
            # 새로 추가
            members_sheet.append_row(members_data[0])
            print(f"✓ 회원 {member_id} 추가 완료")
        
        # 구독권 정보도 동기화
        print("[4/5] 구독권 데이터를 Sheets에 업로드...")
        subscriptions = local_cache.get_member_subscriptions(member_id, include_all=True)
        
        if subscriptions:
            subscriptions_sheet = sheets_sync.spreadsheet.worksheet('member_subscriptions')
            existing_sub_records = subscriptions_sheet.get_all_records()
            existing_sub_ids = [str(s.get('subscription_id', '')) for s in existing_sub_records]
            
            import json
            for sub in subscriptions:
                # daily_limits를 JSON 문자열로 변환
                daily_limits = sub.get('daily_limits', {})
                if isinstance(daily_limits, dict):
                    daily_limits_str = json.dumps(daily_limits)
                else:
                    daily_limits_str = daily_limits
                
                sub_data = [[
                    sub['subscription_id'],
                    sub['member_id'],
                    sub.get('subscription_product_id', ''),
                    sub.get('valid_from', ''),
                    sub.get('valid_until', ''),
                    daily_limits_str,
                    sub.get('status', 'active'),
                ]]
                
                if str(sub['subscription_id']) in existing_sub_ids:
                    # 업데이트
                    row_idx = existing_sub_ids.index(str(sub['subscription_id'])) + 2
                    subscriptions_sheet.update(f'A{row_idx}:G{row_idx}', sub_data)
                    print(f"  ✓ 구독권 {sub['subscription_id']} 업데이트 완료")
                else:
                    # 새로 추가
                    subscriptions_sheet.append_row(sub_data[0])
                    print(f"  ✓ 구독권 {sub['subscription_id']} 추가 완료")
        else:
            print("  구독권 없음 (건너뜀)")
        
        # 금액권 정보도 동기화
        print("[5/6] 금액권 데이터를 Sheets에 업로드...")
        vouchers = local_cache.get_member_vouchers(member_id, include_all=True)
        
        if vouchers:
            vouchers_sheet = sheets_sync.spreadsheet.worksheet('member_vouchers')
            existing_voucher_records = vouchers_sheet.get_all_records()
            existing_voucher_ids = [str(v.get('voucher_id', '')) for v in existing_voucher_records]
            
            for voucher in vouchers:
                voucher_data = [[
                    voucher['voucher_id'],
                    voucher['member_id'],
                    voucher.get('voucher_product_id', ''),
                    voucher.get('original_amount', 0),
                    voucher.get('remaining_amount', 0),
                    voucher.get('parent_voucher_id', ''),
                    voucher.get('valid_from', ''),
                    voucher.get('valid_until', ''),
                    voucher.get('status', 'active'),
                ]]
                
                if str(voucher['voucher_id']) in existing_voucher_ids:
                    # 업데이트
                    row_idx = existing_voucher_ids.index(str(voucher['voucher_id'])) + 2
                    vouchers_sheet.update(f'A{row_idx}:I{row_idx}', voucher_data)
                    print(f"  ✓ 금액권 {voucher['voucher_id']} 업데이트 완료")
                else:
                    # 새로 추가
                    vouchers_sheet.append_row(voucher_data[0])
                    print(f"  ✓ 금액권 {voucher['voucher_id']} 추가 완료")
        else:
            print("  금액권 없음 (건너뜀)")
        
        print("[6/6] 완료!")
        print(f"\n✅ 회원 {member_id} ({member['name']}) 전체 데이터가 Google Sheets에 동기화되었습니다.")
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python sync_member_to_sheets.py <member_id>")
        print("예시: python sync_member_to_sheets.py 20240861")
        sys.exit(1)
    
    member_id = sys.argv[1]
    success = sync_member_to_sheets(member_id)
    sys.exit(0 if success else 1)

