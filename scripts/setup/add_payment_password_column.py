#!/usr/bin/env python3
"""
Google Sheets members 시트에 payment_password 칼럼 추가

실행: python scripts/setup/add_payment_password_column.py
"""

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path


def add_payment_password_column():
    """members 시트에 payment_password 칼럼 추가"""
    
    # 인증 설정
    project_root = Path(__file__).parent.parent.parent
    credentials_path = project_root / 'config' / 'credentials.json'
    spreadsheet_name = 'F-BOX-DB-TEST'
    
    if not credentials_path.exists():
        print(f"❌ credentials.json 파일이 없습니다: {credentials_path}")
        return False
    
    try:
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            str(credentials_path), scope
        )
        
        client = gspread.authorize(creds)
        spreadsheet = client.open(spreadsheet_name)
        sheet = spreadsheet.worksheet('members')
        
        print(f"✓ Google Sheets 연결 성공: {spreadsheet_name}")
        
        # 현재 헤더 확인
        headers = sheet.row_values(1)
        print(f"현재 헤더: {headers}")
        
        if 'payment_password' in headers:
            print("✓ payment_password 칼럼이 이미 존재합니다.")
            return True
        
        # notes 칼럼 앞에 payment_password 추가 (또는 마지막에)
        # 기존 헤더: member_id, name, phone, status, created_at, updated_at, notes
        # 새 헤더: member_id, name, phone, payment_password, status, created_at, updated_at, notes
        
        # status 칼럼 위치 찾기
        if 'status' in headers:
            insert_index = headers.index('status')  # status 앞에 삽입
        elif 'notes' in headers:
            insert_index = headers.index('notes')
        else:
            insert_index = len(headers)  # 마지막에 추가
        
        # 칼럼 삽입 (1-indexed, 헤더가 A1이므로)
        # gspread는 insert_cols 메서드가 없으므로 전체 데이터를 가져와서 수정 후 업데이트
        
        all_data = sheet.get_all_values()
        
        if not all_data:
            print("❌ 시트에 데이터가 없습니다.")
            return False
        
        # 각 행에 payment_password 칼럼 삽입
        new_data = []
        for i, row in enumerate(all_data):
            # 부족한 칼럼 채우기
            while len(row) < insert_index:
                row.append('')
            
            if i == 0:
                # 헤더 행
                new_row = row[:insert_index] + ['payment_password'] + row[insert_index:]
            else:
                # 데이터 행 - 빈 값으로 초기화
                new_row = row[:insert_index] + [''] + row[insert_index:]
            
            new_data.append(new_row)
        
        # 시트 업데이트
        sheet.clear()
        sheet.update('A1', new_data)
        
        # 헤더 포맷팅
        header_len = len(new_data[0])
        sheet.format(f'A1:{chr(64 + header_len)}1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
        
        print(f"✅ payment_password 칼럼 추가 완료! (위치: {insert_index + 1}번째)")
        print(f"새 헤더: {new_data[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    add_payment_password_column()


