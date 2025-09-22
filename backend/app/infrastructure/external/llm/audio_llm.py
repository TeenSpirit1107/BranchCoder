import httpx
from app.infrastructure.config import get_settings
import logging
import tempfile
import io
from pydub import AudioSegment
from pathlib import Path

# 设置模块级别的日志记录器
logger = logging.getLogger(__name__)

class SiliconflowAudioLLM:
    def __init__(self):
        settings = get_settings()
        self.headers = {
            "Authorization": f"Bearer {settings.audio_api_key}",
        }
        self.client = httpx.AsyncClient(
            base_url=settings.audio_api_base,
            headers=self.headers,
            timeout=60.0  # 增加超时时间，因为音频处理可能需要更长时间
        )
        
        self.model_name = settings.audio_model_name
        logger.info(f"Initialized Audio LLM with model: {self.model_name}")
    
    def _convert_audio_to_mp3(self, audio_data: bytes, original_filename: str) -> bytes:
        """将音频数据转换为MP3格式"""
        try:
            # 从文件扩展名推断音频格式
            file_extension = Path(original_filename).suffix.lower().lstrip('.')
            
            # 如果已经是mp3格式，直接返回
            if file_extension == 'mp3':
                logger.info("Audio is already in MP3 format")
                return audio_data
            
            # 支持的音频格式映射
            format_mapping = {
                'wav': 'wav',
                'mp3': 'mp3',
                'flac': 'flac',
                'aac': 'aac',
                'm4a': 'mp4',
                'ogg': 'ogg',
                'wma': 'asf',
                'aiff': 'aiff',
                'au': 'au',
                'mp4': 'mp4',
                'webm': 'webm',
                '3gp': '3gp',
                'amr': 'amr'
            }
            
            # 如果格式不在映射中，尝试自动检测
            audio_format = format_mapping.get(file_extension, file_extension)
            
            logger.info(f"Converting audio from {file_extension} to mp3, original size: {len(audio_data)} bytes")
            
            # 使用临时文件处理音频转换
            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_input:
                temp_input.write(audio_data)
                temp_input.flush()
                temp_input_path = temp_input.name
            
            try:
                # 加载音频文件
                try:
                    audio = AudioSegment.from_file(temp_input_path, format=audio_format)
                except Exception as e:
                    logger.warning(f"Failed to load with format {audio_format}, trying auto-detection: {e}")
                    # 如果指定格式失败，尝试让pydub自动检测
                    audio = AudioSegment.from_file(temp_input_path)
                
                # 转换为MP3格式并保存到临时文件
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_output:
                    temp_output_path = temp_output.name
                
                # 导出为MP3
                audio.export(temp_output_path, format="mp3", bitrate="128k")
                
                # 读取转换后的MP3数据
                with open(temp_output_path, 'rb') as f:
                    mp3_data = f.read()
                    
                logger.info(f"Successfully converted audio to MP3, size: {len(mp3_data)} bytes")
                return mp3_data
                
            finally:
                # 清理临时文件
                try:
                    import os
                    os.unlink(temp_input_path)
                    if 'temp_output_path' in locals():
                        os.unlink(temp_output_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temp files: {cleanup_error}")
                
        except Exception as e:
            logger.exception(f"Error converting audio to MP3: {str(e)}")
            # 如果转换失败，返回原始数据（可能已经是MP3或兼容格式）
            logger.warning("Conversion failed, using original audio data")
            return audio_data
    
    async def audio_to_text(self, audio_file: bytes, filename: str) -> str:
        """将音频文件转换为文本"""
        response = None
        try:
            # 转换音频为MP3格式
            mp3_data = self._convert_audio_to_mp3(audio_file, filename)
            
            # 生成MP3文件名
            mp3_filename = Path(filename).stem + '.mp3'
            
            logger.info(f"Sending audio transcription request for file: {mp3_filename}, size: {len(mp3_data)} bytes")
            
            # 准备表单数据
            files = {
                "file": (mp3_filename, mp3_data, "audio/mp3")
            }
            
            data = {
                "model": self.model_name,
            }
            
            # 发送请求到音频转录接口
            response = await self.client.post(
                "/audio/transcriptions",
                files=files,
                data=data
            )
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                raise Exception(f"API request failed: {response.status_code}")
            
            json_data = response.json()
            
            # 检查响应数据
            if "text" not in json_data:
                logger.error(f"Unexpected response format: {json_data}")
                raise Exception("Invalid response format from API")
            
            transcribed_text = json_data["text"]
            logger.info(f"Successfully transcribed audio, text length: {len(transcribed_text)}")
            
            return transcribed_text
            
        except Exception as e:
            error_msg = f"Error in audio transcription: {str(e)}"
            if response:
                error_msg += f" Response: {response.text if hasattr(response, 'text') else 'No response text'}"
            logger.exception(error_msg)
            raise Exception(error_msg)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
