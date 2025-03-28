import re

def clean_json_string(json_string):
    """
    문자열에서 JSON 파싱을 방해할 수 있는 제어문자 제거
    :param json_string: 입력 문자열
    :return: 정제된 문자열
    """
    if not isinstance(json_string, str):
        return json_string
    return re.sub(r'[\x00-\x1F\x7F]', '', json_string)
