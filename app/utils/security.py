#   AUTO-MAS: A Multi-Script, Multi-Config Management and Automation Software
#   Copyright © 2024-2025 DLmaster361
#   Copyright © 2025-2026 AUTO-MAS Team

#   This file is part of AUTO-MAS.

#   AUTO-MAS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.

#   AUTO-MAS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
#   the GNU Affero General Public License for more details.

#   You should have received a copy of the GNU Affero General Public License
#   along with AUTO-MAS. If not, see <https://www.gnu.org/licenses/>.

#   Contact: DLmaster_361@163.com


import re

from app.utils.secrets import dpapi_decrypt, dpapi_encrypt

__all__ = [
    "sanitize_log_message",
    "format_exception_reason",
    "dpapi_encrypt",
    "dpapi_decrypt",
]


def sanitize_log_message(message: str) -> str:
    """
    从日志消息中移除敏感信息

    :param message: 原始日志消息
    :type message: str
    :return: 过滤后的日志消息
    :rtype: str
    """
    # 定义需要过滤的敏感参数模式，兼容 URL、表单和 JSON 日志格式。
    sensitive_key = (
        r"(?:cdk|password|passwd|pwd|token|access[_-]?token|"
        r"refresh[_-]?token|authorization|cookies?[_-]?str|cookie|"
        r"secret|api[_-]?key|username|phone|cellphone|useridentity|"
        r"(?:s|l|cookie|game|pass)[_-]?token(?:_v2)?|(?:lt|st|account|bbs)_?uid(?:_v2)?|"
        r"(?:lt|account)_?mid(?:_v2)?|mid|cred|oauth[_-]?token|authkey|"
        r"ticket|scan[_-]?code|sms[_-]?code|captcha_output|lot_number|"
        r"geetest_(?:challenge|validate|seccode)|x-community-session|"
        r"(?:Miyoushe|Skland|Kuro|Taygedo|CloudGenshin|Yunma)Token)"
    )
    sensitive_patterns = [
        # JSON 字符串值，例如 "password": "..."
        (rf"([\"']{sensitive_key}[\"']\s*:\s*[\"'])(.*?)([\"'])", r"\1***\3"),
        # JSON 数字、布尔或未加引号值，例如 "uid": ...（仅匹配敏感 key）
        (rf"([\"']{sensitive_key}[\"']\s*:\s*)(?![\"'])([^,}}\]]+)", r"\1***"),
        # URL、表单和普通日志中的 key=value
        (rf"(\b{sensitive_key}\b\s*=\s*)([^&\s,}}\]]+)", r"\1***"),
        # 请求头或字典中的 key: value
        (rf"(\b{sensitive_key}\b\s*:\s*)([^\r\n,}}\]]+)", r"\1***"),
    ]

    sanitized_message = message
    for pattern, replacement in sensitive_patterns:
        sanitized_message = re.sub(
            pattern, replacement, sanitized_message, flags=re.IGNORECASE
        )

    # 请求 URL 仅保留协议、主机和路径；不将查询参数或代理账号写入诊断文件。
    sanitized_message = re.sub(
        r"(https?://)[^/\s@]+@", r"\1***@", sanitized_message, flags=re.IGNORECASE
    )
    sanitized_message = re.sub(
        r"(https?://[^\s?#]+)[?#][^\s]*",
        r"\1",
        sanitized_message,
        flags=re.IGNORECASE,
    )
    sanitized_message = re.sub(r"\b1[3-9]\d{9}\b", "***", sanitized_message)
    return re.sub(r"\b[A-Za-z0-9_-]{32,}\b", "***", sanitized_message)


def format_exception_reason(
    error: BaseException,
    *,
    stage: str,
    include_message: bool = True,
) -> str:
    """生成不为空且不包含 URL 查询参数的异常原因。"""

    exception_name = type(error).__name__
    message = sanitize_log_message(str(error).strip()) if include_message else ""
    message = re.sub(
        r"(https?://[^\s?#]+)[?#][^\s]*",
        r"\1",
        message,
        flags=re.IGNORECASE,
    )
    if not message:
        if "timeout" in exception_name.lower():
            message = "请求超时"
        elif include_message:
            message = "未提供异常详情"
        else:
            message = "程序内部异常"
    return f"{stage}（{exception_name}）：{message}"
