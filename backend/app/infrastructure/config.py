from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    # Bypass
    bypass_oauth2: bool = False
    
    # Database configuration
    database_type: str = "sqlite"  # 可选值: memory, sqlite
    database_url: str = "sqlite+aiosqlite:///./data/ai_manus.db"
    database_echo: bool = False  # 是否打印SQL语句
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # Model provider configuration
    api_key: str | None = None
    api_base: str = "https://api.deepseek.com/v1"
    
    # Model configuration
    model_name: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 2000

    # Image model configuration
    image_api_key: str | None = None
    image_api_base: str = "https://api.openai.com/v1"
    image_model_name: str = "dall-e-3"

    # Audio model configuration
    audio_api_key: str | None = None
    audio_api_base: str = "https://api.siliconflow.cn/v1"
    audio_model_name: str = "FunAudioLLM/SenseVoiceSmall"
    
    # Video model configuration
    video_api_key: str | None = None
    video_api_base: str = "https://generativelanguage.googleapis.com"
    video_model_name: str = "gemini-2.5-flash-preview-05-20"
    
    # Reasoning model configuration
    reason_api_key: str | None = None
    reason_api_base: str = "https://api.deepseek.com/v1"
    reason_model_name: str = "o3"
    
    # Docker configuration
    docker_host_url: str | None = None  # 远程Docker API地址，如"tcp://192.168.1.100:2375"
    docker_timeout: int | None = 120  # Docker API超时时间(秒)
    docker_tls_verify: bool = False  # 是否验证TLS证书
    docker_cert_path: str | None = None  # TLS证书路径
    
    # Sandbox configuration
    sandbox_remote_address: str | None = None  # 远程沙盒服务地址（供远程Docker使用）
    sandbox_image: str | None = None
    sandbox_name_prefix: str | None = None
    sandbox_ttl_minutes: int | None = 30
    sandbox_network: str | None = None  # Docker network bridge name
    sandbox_chrome_args: str | None = ""
    sandbox_https_proxy: str | None = None
    sandbox_http_proxy: str | None = None
    sandbox_no_proxy: str | None = None
    
    # Sandbox security configuration
    sandbox_run_as_user: int = 0  # 允许root用户（0）
    sandbox_run_as_group: int = 0  # 允许root组（0）
    sandbox_fs_group: int = 1000  # 文件系统组ID保持1000
    sandbox_allow_privilege_escalation: bool = True  # 允许权限提升（sudo需要）
    sandbox_read_only_root_filesystem: bool = False  # 允许写入根文件系统
    
    # Kubernetes configuration
    use_kubernetes: bool = False  # 是否使用Kubernetes沙箱
    k8s_namespace: str | None = None  # Kubernetes命名空间
    k8s_release_name: str | None = None  # Helm Release名称，用于构造ServiceAccount名称
    k8s_service_type: str = "ClusterIP"  # Kubernetes服务类型（ClusterIP或NodePort）
    k8s_node_selector: str | None = None  # Kubernetes节点选择器（JSON格式）
    k8s_resources_limits_cpu: str | None = None  # CPU限制，如"500m"
    k8s_resources_limits_memory: str | None = None  # 内存限制，如"512Mi"
    k8s_resources_requests_cpu: str | None = None  # CPU请求，如"100m"
    k8s_resources_requests_memory: str | None = None  # 内存请求，如"128Mi"
    
    # 持久化存储卷配置
    k8s_enable_persistent_volume: bool = True  # 是否启用持久化存储卷
    k8s_pvc_size: str = "10Gi"  # PVC大小，如"10Gi"
    k8s_storage_class: str | None = None  # 存储类名称，None表示使用默认存储类
    k8s_volume_mount_path: str = "/home/ubuntu"  # 存储卷挂载路径
    
    # Docker持久化存储卷配置
    docker_enable_persistent_volume: bool = True  # 是否启用Docker持久化存储卷
    docker_volume_mount_path: str = "/home/ubuntu"  # Docker存储卷挂载路径
    
    # Search engine configuration
    search_engine_type: str = "searxng"  # 可选值: google, searxng
    google_search_api_key: str | None = None
    google_search_engine_id: str | None = None
    searxng_url: str | None = None
    
    # Code Server configuration
    code_server_origin: str = "localhost.betterspace.top"  # 主域名
    code_server_subdomain_pattern: str = "code-{agent_id}"  # 子域名模式
    
    # Logging configuration
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    def validate(self):
        if not self.api_key:
            raise ValueError("API key is required")

def get_settings() -> Settings:
    settings = Settings()
    settings.validate()
    return settings 
