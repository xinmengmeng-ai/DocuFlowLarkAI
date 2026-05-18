"""
配置管理模块
"""
import os
import shutil
import sys
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

from cryptography.fernet import Fernet, InvalidToken

# 项目根目录（兼容 PyInstaller 冻结运行）
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = BASE_DIR

DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
LOGS_DIR = DATA_DIR / "logs"
DB_DIR = DATA_DIR / "db"
CONFIG_DIR = BASE_DIR / "config"
TEMPLATES_DIR = BASE_DIR / "templates"


def _bootstrap_runtime_dirs() -> None:
    """
    冻结运行时将内置资源同步到可写目录。
    前端资源属于程序资产，每次启动都刷新，避免升级后继续加载旧页面。
    其余目录仅在目标不存在时初始化，避免覆盖用户数据。
    """
    if not getattr(sys, "frozen", False):
        return

    frontend_src = RESOURCE_DIR / "frontend"
    frontend_dst = BASE_DIR / "frontend"
    if frontend_src.exists():
        if frontend_src.is_dir():
            shutil.copytree(frontend_src, frontend_dst, dirs_exist_ok=True)
        else:
            frontend_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(frontend_src, frontend_dst)

    for name in ("templates", "config"):
        src = RESOURCE_DIR / name
        dst = BASE_DIR / name
        if dst.exists() or not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    for src_name, dst_name in (("data/templates.json", "data/templates.json"),):
        src = RESOURCE_DIR / src_name
        dst = BASE_DIR / dst_name
        if dst.exists() or not src.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


_bootstrap_runtime_dirs()

# 确保目录存在
for d in [DATA_DIR, CACHE_DIR, LOGS_DIR, DB_DIR, CONFIG_DIR, TEMPLATES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


SECRET_PREFIX = "enc:v1:"
SENSITIVE_CONFIG_KEYS = {
    "app_secret",
    "api_key",
    "cloud_api_key",
    "verification_token",
    "encrypt_key",
}
_secret_cipher: Optional[Fernet] = None


def _get_secret_key_file() -> Path:
    """获取本机密钥文件路径（不放在项目目录内）"""
    custom_path = os.getenv("DOCUFLOW_SECRET_KEY_FILE")
    if custom_path:
        return Path(custom_path).expanduser()

    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        base_dir = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
        return base_dir / "DocuFlowLarkAI" / "secret.key"

    return Path.home() / ".config" / "DocuFlowLarkAI" / "secret.key"


def _load_or_create_secret_key() -> bytes:
    """加载或创建本机对称密钥"""
    env_key = os.getenv("DOCUFLOW_MASTER_KEY")
    if env_key:
        return env_key.encode("utf-8")

    key_file = _get_secret_key_file()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        raw = key_file.read_bytes().strip()
        if raw:
            return raw

    key = Fernet.generate_key()
    key_file.write_bytes(key)
    return key


def _get_secret_cipher() -> Fernet:
    global _secret_cipher
    if _secret_cipher is None:
        _secret_cipher = Fernet(_load_or_create_secret_key())
    return _secret_cipher


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    """加密单个敏感值（空值不加密）"""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if value == "":
        return ""
    if value.startswith(SECRET_PREFIX):
        return value
    token = _get_secret_cipher().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{SECRET_PREFIX}{token}"


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    """解密单个敏感值（非加密格式原样返回）"""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    if not value.startswith(SECRET_PREFIX):
        return value
    token = value[len(SECRET_PREFIX):]
    try:
        return _get_secret_cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def protect_config_data(data: Any) -> Any:
    """递归加密配置中的敏感字段"""
    if isinstance(data, dict):
        protected: Dict[str, Any] = {}
        for key, value in data.items():
            if key in SENSITIVE_CONFIG_KEYS and isinstance(value, str):
                protected[key] = encrypt_secret(value)
            else:
                protected[key] = protect_config_data(value)
        return protected
    if isinstance(data, list):
        return [protect_config_data(item) for item in data]
    return data


def reveal_config_data(data: Any) -> Any:
    """递归解密配置中的敏感字段"""
    if isinstance(data, dict):
        revealed: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str) and (key in SENSITIVE_CONFIG_KEYS or value.startswith(SECRET_PREFIX)):
                revealed[key] = decrypt_secret(value)
            else:
                revealed[key] = reveal_config_data(value)
        return revealed
    if isinstance(data, list):
        return [reveal_config_data(item) for item in data]
    return data


class FeishuConfig(BaseModel):
    """飞书配置"""
    app_id: str = ""
    app_secret: str = ""
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    base_url: str = "https://open.feishu.cn/open-apis"
    mcp_url: str = "https://mcp.feishu.cn/mcp"
    timeout: int = 30
    max_retries: int = 3
    
    # 上传配置
    batch_size: int = 1000
    concurrent_limit: int = 5
    retry_attempts: int = 3
    
    # 知识库配置
    default_space_id: Optional[str] = None
    auto_create_space: bool = True


class LLMProviderConfig(BaseModel):
    """LLM提供商配置"""
    enabled: bool = False
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4-turbo-preview"
    temperature: float = 0.3
    max_tokens: int = 4000
    timeout: int = 60


class LLMConfig(BaseModel):
    """LLM配置"""
    providers: dict = Field(default_factory=dict)
    
    # 处理配置
    content_clean: bool = True
    generate_summary: bool = True
    extract_keywords: bool = True
    auto_classify: bool = True
    quality_check: bool = True
    min_score: int = 70
    max_retry: int = 3
    
    def __init__(self, **data):
        # 定义默认提供商配置（作为后备）
        default_providers = {
            "openai": {"enabled": False, "model": "gpt-4-turbo-preview", "base_url": "https://api.openai.com"},
            "claude": {"enabled": False, "model": "claude-3-sonnet-20240229", "base_url": "https://api.anthropic.com"},
            "qwen": {"enabled": False, "model": "qwen-max", "base_url": "https://dashscope.aliyuncs.com/api/v1"},
            "ollama": {"enabled": False, "model": "llama2-chinese", "base_url": "http://localhost:11434"},
            "deepseek": {"enabled": False, "model": "deepseek-chat", "base_url": "https://api.deepseek.com"},
            "kimi": {"enabled": False, "model": "moonshot-v1-8k", "base_url": "https://api.moonshot.cn"},
            "mock": {"enabled": False, "model": "mock", "base_url": "http://localhost/mock"}
        }
        
        # 如果传入了 providers，需要与默认配置合并
        if data.get('providers'):
            merged_providers = {}
            raw_providers = data['providers']
            
            # 先处理传入的 providers
            for name, provider_data in raw_providers.items():
                if isinstance(provider_data, dict):
                    # 获取默认值并更新
                    default = default_providers.get(name, {}).copy()
                    default.update(provider_data)
                    merged_providers[name] = LLMProviderConfig(**default)
                elif isinstance(provider_data, LLMProviderConfig):
                    # 已经是 LLMProviderConfig 对象
                    merged_providers[name] = provider_data
                else:
                    # 其他类型，尝试用默认配置
                    default = default_providers.get(name, {}).copy()
                    if hasattr(provider_data, 'dict'):
                        default.update(provider_data.dict())
                    merged_providers[name] = LLMProviderConfig(**default)
            
            # 对于未传入但有默认配置的 provider，也要加入（保持enabled=False）
            for name, default in default_providers.items():
                if name not in merged_providers:
                    merged_providers[name] = LLMProviderConfig(**default)
            
            data['providers'] = merged_providers
        else:
            # 没有传入 providers，使用全部默认配置（都未启用）
            data['providers'] = {name: LLMProviderConfig(**cfg) for name, cfg in default_providers.items()}
        
        # 调用父类初始化
        super().__init__(**data)


class MinerUConfig(BaseModel):
    """MinerU配置"""
    use_local: bool = True
    local_url: str = "http://localhost:8000"
    cloud_api_key: Optional[str] = None
    cloud_url: str = "https://mineru.net/api/v1"
    timeout: int = 300
    
    # 解析选项
    extract_images: bool = True
    extract_tables: bool = True
    ocr_enabled: bool = True
    language: str = "zh"
    return_format: str = "markdown"


class AppConfig(BaseSettings):
    """应用配置"""
    # 应用信息
    app_name: str = "企业知识库迁移系统"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 服务器配置
    host: str = "127.0.0.1"
    port: int = 8000
    
    # 数据库
    database_url: str = f"sqlite+aiosqlite:///{DB_DIR}/app.db"
    
    # Redis配置 (如需Celery可启用)
    # redis_url: str = "redis://localhost:6379/0"
    
    # 子配置
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mineru: MinerUConfig = Field(default_factory=MinerUConfig)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取配置实例"""
    global _config
    if _config is None:
        _config = AppConfig()
        # 尝试从YAML文件加载配置
        _load_yaml_configs(_config)
    return _config


def _load_yaml_configs(config: AppConfig):
    """从YAML文件加载配置"""
    import logging
    logger = logging.getLogger(__name__)

    def _rewrite_if_needed(path: Path, raw_data: Dict[str, Any]):
        protected_data = protect_config_data(raw_data)
        if protected_data == raw_data:
            return
        with open(path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(protected_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    # 加载飞书配置
    feishu_yaml = CONFIG_DIR / "feishu.yaml"
    if feishu_yaml.exists():
        try:
            with open(feishu_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    decrypted = reveal_config_data(data)
                    config.feishu = FeishuConfig(**decrypted)
                    _rewrite_if_needed(feishu_yaml, data)
                    logger.info(f"已加载飞书配置: app_id={config.feishu.app_id[:10]}...")
        except Exception as e:
            logger.error(f"加载飞书配置失败: {e}")
    
    # 加载LLM配置
    llm_yaml = CONFIG_DIR / "llm.yaml"
    if llm_yaml.exists():
        try:
            with open(llm_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    decrypted = reveal_config_data(data)
                    config.llm = LLMConfig(**decrypted)
                    _rewrite_if_needed(llm_yaml, data)
                    # 检查哪些provider启用了
                    enabled_providers = []
                    for name, provider in config.llm.providers.items():
                        if hasattr(provider, 'enabled') and provider.enabled:
                            enabled_providers.append(name)
                    logger.info(f"已加载LLM配置: 启用={enabled_providers}")
        except Exception as e:
            logger.error(f"加载LLM配置失败: {e}")
    
    # 加载MinerU配置
    mineru_yaml = CONFIG_DIR / "mineru.yaml"
    if mineru_yaml.exists():
        try:
            with open(mineru_yaml, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    decrypted = reveal_config_data(data)
                    config.mineru = MinerUConfig(**decrypted)
                    _rewrite_if_needed(mineru_yaml, data)
                    logger.info(f"已加载MinerU配置: use_local={config.mineru.use_local}")
        except Exception as e:
            logger.error(f"加载MinerU配置失败: {e}")


def reload_config():
    """重新加载配置"""
    global _config
    _config = None
    return get_config()
