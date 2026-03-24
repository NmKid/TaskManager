import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
import google.generativeai as genai
import os
import time
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

class GeminiAdapter:
    """
    Google Generative AI (Gemini) API と連携するためのアダプタクラス。
    タスク名やメモから、重要度・緊急度・所要時間・場所などの「タスクの属性」を推定したり、
    所要時間が長いタスクをサブタスクに分割する役割を担う。
    """
    def __init__(self):
        # APIキーは環境変数から取得するか、Config経由で取得する
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Gemini APIキーが見つかりません。\n"
                "プロジェクトフォルダ直下にある「.env.example」をコピーして「.env」ファイルを作成し、\n"
                "GEMINI_API_KEY=あなたのAPIキー を設定してください。"
            )
        
        # APIバージョンの指定 (v1beta -> v1)
        genai.configure(api_key=api_key, transport='rest', client_options={'api_endpoint': 'generativelanguage.googleapis.com'})
        
        # モデルの初期化 (gemini-2.5-pro を想定)
        self.model = genai.GenerativeModel('gemini-2.5-pro')

    def generate_content_with_retry(self, prompt: str, max_retries: int = 3) -> any:
        """
        503等の容量不足エラーに対応するため、リトライ処理を挟んでAIによる生成を行う。
        """
        for count in range(max_retries):
            try:
                return self.model.generate_content(prompt)
            except Exception as e:
                error_msg = str(e)
                # 503 Unavailable や Capacity Exhausted に対処
                if "503" in error_msg or "UNAVAILABLE" in error_msg or "CAPACITY" in error_msg.upper():
                    if count < max_retries - 1:
                        sleep_time = (count + 1) * 15 # 15秒, 30秒と待機時間を増やす
                        print(f"Gemini APIが混雑しています(503)。{sleep_time}秒後にリトライします... ({count+1}/{max_retries})")
                        time.sleep(sleep_time)
                        continue
                # リトライ不可なエラー、または最大リトライ到達時
                print(f"Gemini APIリクエストエラー: {e}")
                raise e


    def analyze_task(self, title: str, notes: str) -> dict:
        """
        タスク名とメモを元に、タスクの詳細情報をAIで解析しJSON形式で返す。
        """
        prompt = f'''
以下のタスクを分析し、JSON形式で出力してください。
タスク名: {title}
メモ: {notes}

出力形式は必ず以下の構造を持つJSONデータのみとしてください。
{{
  "duration_minutes": 推定所要時間(数値),
  "importance": 1(低)～5(高)の数値,
  "location": "場所の推定（無ければ null）",
  "recommended_subtasks": ["サブタスク1", "サブタスク2"] (分割不要な場合は空配列)
}}
所要時間が60分を超えるか、工程が複数ある場合は recommended_subtasks に分割したタスク名を含めてください。
'''
        # AIに問い合わせ (リトライ付き)
        try:
            response = self.generate_content_with_retry(prompt)
        except Exception:
            return {
                "duration_minutes": 30,
                "importance": 3,
                "location": None,
                "recommended_subtasks": []
            }
        
        # JSONのパース処理 (簡易的な抽出)
        try:
            import json
            import re
            
            # Markdownのコードブロックなどで囲まれている場合に対処
            text = response.text
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
                
            return json.loads(text)
        except Exception as e:
            print(f"Gemini解析エラー: {e}\nRaw Response: {response.text}")
            # 解析失敗時のデフォルト値
            return {
                "duration_minutes": 30,
                "importance": 3,
                "location": None,
                "recommended_subtasks": []
            }

    def sort_tasks_order(self, tasks_data: list) -> dict:
        """
        対象リストの未スケジュールタスク群(辞書配列)を受け取り、AIで重複を検知・排除した上で
        最適な実行順序に並び替えた結果を返す。
        戻り値: {"sorted": [タスクオブジェクト...], "duplicates": [タスクオブジェクト...]}
        """
        if not tasks_data or len(tasks_data) <= 1:
            return {"sorted": tasks_data, "duplicates": []}
            
        tasks_text = ""
        for item in tasks_data:
            t = item["task"]
            tid = t.get('id')
            title = t.get('title', '')
            notes = t.get('notes', '')
            due = t.get('due', 'なし')
            tasks_text += f"ID: {tid}\nタイトル: {title}\n期限: {due}\nメモ: {notes}\n---\n"

        prompt = f'''
以下のタスク群を分析し、内容が完全に重複しているタスク（全く同じ意味・目的のタスク）があれば片方を削除対象としてください。
残ったタスクについて、最も効率的かつ合理的な順番（特に期限情報を重視）で実行するための最適な並び順を検討してください。
出力は、必ず以下のキーを持つJSONオブジェクトとしてください。それ以外のテキストは一切含めないでください。
- "sorted_ids": 実行するタスクのIDを最適な順序で並べた配列
- "duplicate_ids": 重複として削除（無視）すべきと判定したタスクのIDの配列（重複がない場合は空配列）

【タスク一覧】
{tasks_text}

【出力形式の例】
{{
  "sorted_ids": ["id_C", "id_A"],
  "duplicate_ids": ["id_B"]
}}
'''
        # 失敗時のフェイルセーフ用（元の順序をそのまま返す）
        fallback_result = {"sorted": tasks_data, "duplicates": []}
        
        try:
            response = self.generate_content_with_retry(prompt)
        except Exception as e:
            print(f"タスク並び替えAPIエラー: {e}")
            return fallback_result
            
        try:
            import json
            import re
            
            text = response.text
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
                
            result_json = json.loads(text)
            if isinstance(result_json, dict) and "sorted_ids" in result_json:
                sorted_ids = result_json.get("sorted_ids", [])
                duplicate_ids = result_json.get("duplicate_ids", [])
                
                id_to_task = {item["task"]["id"]: item for item in tasks_data}
                
                result_tasks = []
                for sid in sorted_ids:
                    if sid in id_to_task and id_to_task[sid] not in result_tasks:
                        result_tasks.append(id_to_task[sid])
                        
                duplicate_tasks = []
                for did in duplicate_ids:
                    if did in id_to_task and id_to_task[did] not in duplicate_tasks and id_to_task[did] not in result_tasks:
                        duplicate_tasks.append(id_to_task[did])
                
                # AIが漏らした（sortedにもduplicateにもない）IDについて、フェイルセーフとして末尾に付け足す
                for item in tasks_data:
                    if item not in result_tasks and item not in duplicate_tasks:
                        result_tasks.append(item)
                        
                return {"sorted": result_tasks, "duplicates": duplicate_tasks}
            else:
                return fallback_result
        except Exception as e:
            print(f"タスク並び替え解析/重複検知エラー: {e}")
            return fallback_result
