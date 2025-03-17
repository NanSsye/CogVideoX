import os
import json
import tomllib
import traceback
import uuid
import time
import asyncio
import aiohttp
from typing import Dict, Optional, List
from collections import defaultdict
import base64
import re

from loguru import logger
from zhipuai import ZhipuAI  # 需要安装 zhipuai 库

from WechatAPI import WechatAPIClient
from database.XYBotDB import XYBotDB
from utils.plugin_base import PluginBase
from utils.decorators import on_text_message, on_image_message


class CogVideoX(PluginBase):
    """基于智谱AI CogVideoX的视频生成插件，支持自定义分辨率和比例"""
    
    description = "基于智谱AI CogVideoX的视频生成插件，支持自定义分辨率和比例"
    author = "老夏的金库"
    version = "1.1.0"
    
    def __init__(self):
        super().__init__()
        
        try:
            # 读取配置
            config_path = os.path.join(os.path.dirname(__file__), "config.toml")
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
                
            # 获取CogVideoX配置
            plugin_config = config.get("CogVideoX", {})
            self.enable = plugin_config.get("enable", True)
            self.api_key = plugin_config.get("api_key", "")
            self.model = plugin_config.get("model", "cogvideox-2")
            
            # 获取命令配置
            self.generate_commands = plugin_config.get("generate_commands", ["#生成视频"])
            self.image_generate_commands = plugin_config.get("image_generate_commands", ["#图生视频"])
            self.query_commands = plugin_config.get("query_commands", ["#查询视频"])
            self.exit_commands = plugin_config.get("exit_commands", ["#结束对话", "#退出对话"])
            
            # 获取积分配置
            self.enable_points = plugin_config.get("enable_points", True)
            self.generate_cost = plugin_config.get("generate_cost", 20)
            
            # 获取视频保存配置
            self.save_path = plugin_config.get("save_path", "temp")
            self.save_dir = os.path.join(os.path.dirname(__file__), self.save_path)
            os.makedirs(self.save_dir, exist_ok=True)
            
            # 获取默认分辨率和比例
            self.default_size = plugin_config.get("default_size", "1920x1080")
            self.default_ratio = plugin_config.get("default_ratio", "16:9")
            
            # 获取管理员列表
            self.admins = plugin_config.get("admins", [])
            
            # 初始化ZhipuAI客户端
            self.client = ZhipuAI(api_key=self.api_key)
            
            # 初始化数据库
            self.db = XYBotDB()
            
            # 初始化会话状态
            self.conversations = defaultdict(dict)  # 用户ID -> {task_id: str, status: str, last_image: str}
            self.conversation_expiry = 3600  # 会话过期时间(秒)
            self.conversation_timestamps = {}  # 用户ID -> 最后活动时间
            
            # 验证关键配置
            if not self.api_key:
                logger.warning("CogVideoX插件未配置API密钥")
                
            logger.info("CogVideoX插件初始化成功")
            
        except Exception as e:
            logger.error(f"CogVideoX插件初始化失败: {str(e)}")
            logger.error(traceback.format_exc())
            self.enable = False
    
    async def async_init(self):
        """异步初始化"""
        pass
    
    def _parse_command(self, content: str) -> tuple[str, Optional[str], Optional[str]]:
        """解析命令中的提示词、分辨率和比例"""
        size_pattern = r"--size\s+(\d+x\d+)"
        ratio_pattern = r"--ratio\s+(\d+:\d+)"
        
        size_match = re.search(size_pattern, content)
        ratio_match = re.search(ratio_pattern, content)
        
        prompt = re.sub(r"--size\s+\d+x\d+\s*|--ratio\s+\d+:\d+\s*", "", content).strip()
        
        size = size_match.group(1) if size_match else self.default_size
        ratio = ratio_match.group(1) if ratio_match else self.default_ratio
        
        if not re.match(r"^\d+x\d+$", size):
            size = self.default_size
        
        if not re.match(r"^\d+:\d+$", ratio):
            ratio = self.default_ratio
        
        return prompt, size, ratio
    
    @on_text_message(priority=30)
    async def handle_text_commands(self, bot: WechatAPIClient, message: dict) -> bool:
        """处理文本命令"""
        if not self.enable:
            return True
        
        content = message.get("Content", "").strip()
        from_wxid = message.get("FromWxid", "")
        sender_wxid = message.get("SenderWxid", "")
        
        # 清理过期的会话
        self._cleanup_expired_conversations()
        
        # 会话标识
        conversation_key = f"{from_wxid}_{sender_wxid}"
        
        # 检查是否是结束对话命令
        if content in self.exit_commands:
            if conversation_key in self.conversations:
                del self.conversations[conversation_key]
                if conversation_key in self.conversation_timestamps:
                    del self.conversation_timestamps[conversation_key]
                await bot.send_at_message(from_wxid, "\n已结束CogVideoX视频生成对话", [sender_wxid])
                return False
            else:
                await bot.send_at_message(from_wxid, "\n您当前没有活跃的CogVideoX对话", [sender_wxid])
                return False
        
        # 检查是否是文生视频命令
        for cmd in self.generate_commands:
            if content.startswith(cmd):
                prompt, size, ratio = self._parse_command(content[len(cmd):].strip())
                if not prompt:
                    await bot.send_at_message(from_wxid, "\n请提供视频描述，格式：#生成视频 [描述] [--size 宽度x高度] [--ratio 宽:高]", [sender_wxid])
                    return False
                
                if not self.api_key:
                    await bot.send_at_message(from_wxid, "\n请先在配置文件中设置CogVideoX API密钥", [sender_wxid])
                    return False
                
                # 检查积分
                if self.enable_points and sender_wxid not in self.admins:
                    points = self.db.get_points(sender_wxid)
                    if points < self.generate_cost:
                        await bot.send_at_message(from_wxid, f"\n您的积分不足，生成视频需要{self.generate_cost}积分，您当前有{points}积分", [sender_wxid])
                        return False
                
                try:
                    await bot.send_at_message(from_wxid, "\n正在提交视频生成任务，请稍候...", [sender_wxid])
                    
                    task_response = await self._generate_video_from_text(prompt, size)
                    if task_response and task_response.task_status == "PROCESSING":
                        task_id = task_response.id
                        request_id = task_response.request_id or "N/A"
                        
                        if self.enable_points and sender_wxid not in self.admins:
                            self.db.add_points(sender_wxid, -self.generate_cost)
                            points_msg = f"已扣除{self.generate_cost}积分，剩余{points - self.generate_cost}积分"
                        else:
                            points_msg = ""
                        
                        await bot.send_at_message(
                            from_wxid, 
                            f"\n视频生成任务已提交！\n任务ID: {task_id}\n请求ID: {request_id}\n分辨率: {size}\n比例: {ratio}\n{points_msg}\n任务处理中，将自动发送视频。",
                            [sender_wxid]
                        )
                        
                        self.conversations[conversation_key]["task_id"] = task_id
                        self.conversations[conversation_key]["status"] = "PROCESSING"
                        self.conversation_timestamps[conversation_key] = time.time()
                        
                        asyncio.create_task(self._check_task_result(bot, from_wxid, sender_wxid, task_id))
                    else:
                        await bot.send_at_message(from_wxid, "\n视频生成任务提交失败，请稍后再试", [sender_wxid])
                except Exception as e:
                    logger.error(f"生成视频失败: {str(e)}")
                    logger.error(traceback.format_exc())
                    await bot.send_at_message(from_wxid, f"\n生成视频失败: {str(e)}", [sender_wxid])
                return False
        
        # 检查是否是图生视频命令
        for cmd in self.image_generate_commands:
            if content.startswith(cmd):
                prompt, size, ratio = self._parse_command(content[len(cmd):].strip())
                if not prompt:
                    await bot.send_at_message(from_wxid, "\n请提供提示词，格式：#图生视频 [描述] [--size 宽度x高度] [--ratio 宽:高]", [sender_wxid])
                    return False
                
                if not self.api_key:
                    await bot.send_at_message(from_wxid, "\n请先在配置文件中设置CogVideoX API密钥", [sender_wxid])
                    return False
                
                last_image = self.conversations[conversation_key].get("last_image")
                if not last_image:
                    await bot.send_at_message(from_wxid, "\n请先发送一张图片后再使用此命令", [sender_wxid])
                    return False
                
                if self.enable_points and sender_wxid not in self.admins:
                    points = self.db.get_points(sender_wxid)
                    if points < self.generate_cost:
                        await bot.send_at_message(from_wxid, f"\n您的积分不足，生成视频需要{self.generate_cost}积分，您当前有{points}积分", [sender_wxid])
                        return False
                
                try:
                    await bot.send_at_message(from_wxid, "\n正在基于图片生成视频，请稍候...", [sender_wxid])
                    
                    task_response = await self._generate_video_from_image(last_image, prompt, size)
                    if task_response and task_response.task_status == "PROCESSING":
                        task_id = task_response.id
                        request_id = task_response.request_id or "N/A"
                        
                        if self.enable_points and sender_wxid not in self.admins:
                            self.db.add_points(sender_wxid, -self.generate_cost)
                            points_msg = f"已扣除{self.generate_cost}积分，剩余{points - self.generate_cost}积分"
                        else:
                            points_msg = ""
                        
                        await bot.send_at_message(
                            from_wxid, 
                            f"\n图生视频任务已提交！\n任务ID: {task_id}\n请求ID: {request_id}\n分辨率: {size}\n比例: {ratio}\n{points_msg}\n任务处理中，将自动发送视频。",
                            [sender_wxid]
                        )
                        
                        self.conversations[conversation_key]["task_id"] = task_id
                        self.conversations[conversation_key]["status"] = "PROCESSING"
                        self.conversation_timestamps[conversation_key] = time.time()
                        
                        asyncio.create_task(self._check_task_result(bot, from_wxid, sender_wxid, task_id))
                    else:
                        await bot.send_at_message(from_wxid, "\n图生视频任务提交失败，请稍后再试", [sender_wxid])
                except Exception as e:
                    logger.error(f"图生视频失败: {str(e)}")
                    logger.error(traceback.format_exc())
                    await bot.send_at_message(from_wxid, f"\n生成视频失败: {str(e)}", [sender_wxid])
                return False
        
        # 检查是否是查询命令
        for cmd in self.query_commands:
            if content.startswith(cmd):
                task_id = content[len(cmd):].strip()
                if not task_id:
                    await bot.send_at_message(from_wxid, "\n请提供任务ID，格式：#查询视频 [任务ID]", [sender_wxid])
                    return False
                
                try:
                    result = await self._retrieve_video_result(task_id)
                    if result:
                        status = result.task_status
                        if status == "SUCCESS":
                            video_url = result.video_result[0].url
                            cover_url = result.video_result[0].cover_image_url
                            await bot.send_at_message(
                                from_wxid, 
                                f"\n视频生成完成！\n视频URL: {video_url}\n封面URL: {cover_url}", 
                                [sender_wxid]
                            )
                        elif status == "FAIL":
                            await bot.send_at_message(from_wxid, "\n视频生成失败！", [sender_wxid])
                        else:
                            await bot.send_at_message(from_wxid, "\n任务仍在处理中，请稍后再试", [sender_wxid])
                    else:
                        await bot.send_at_message(from_wxid, "\n查询失败，请检查任务ID", [sender_wxid])
                except Exception as e:
                    logger.error(f"查询视频结果失败: {str(e)}")
                    await bot.send_at_message(from_wxid, f"\n查询失败: {str(e)}", [sender_wxid])
                return False
        
        return True
    
    @on_image_message(priority=30)
    async def handle_image(self, bot: WechatAPIClient, message: dict) -> bool:
        """处理图片消息，缓存图片数据，不发送提示"""
        if not self.enable:
            return True
        
        from_wxid = message.get("FromWxid", "")
        sender_wxid = message.get("SenderWxid", "")
        
        conversation_key = f"{from_wxid}_{sender_wxid}"
        
        image_data = message.get("Content", "")
        if not image_data or not isinstance(image_data, str):
            return True
        
        self.conversations[conversation_key]["last_image"] = image_data
        self.conversation_timestamps[conversation_key] = time.time()
        
        return True
    
    async def _generate_video_from_text(self, prompt: str, size: str) -> Optional[Dict]:
        """调用文生视频API"""
        try:
            response = await asyncio.to_thread(
                self.client.videos.generations,
                model=self.model,
                prompt=prompt,
                quality="quality",
                with_audio=True,
                size=size,
                fps=30
            )
            return response
        except Exception as e:
            logger.error(f"文生视频失败: {str(e)}")
            return None
    
    async def _generate_video_from_image(self, image_data: str, prompt: str, size: str) -> Optional[Dict]:
        """调用图生视频API"""
        try:
            response = await asyncio.to_thread(
                self.client.videos.generations,
                model=self.model,
                image_url=image_data,
                prompt=prompt,
                quality="speed",
                with_audio=True,
                size=size,
                fps=30
            )
            return response
        except Exception as e:
            logger.error(f"图生视频失败: {str(e)}")
            return None
    
    async def _retrieve_video_result(self, task_id: str) -> Optional[Dict]:
        """查询视频生成结果"""
        try:
            response = await asyncio.to_thread(
                self.client.videos.retrieve_videos_result,
                id=task_id
            )
            return response
        except Exception as e:
            logger.error(f"查询视频结果失败: {str(e)}")
            return None
    
    async def _download_video(self, video_url: str) -> bytes:
        """下载视频文件"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.get(video_url) as response:
                    if response.status == 200:
                        video_data = await response.read()
                        logger.debug(f"下载的视频数据大小: {len(video_data)} bytes")
                        return video_data
                    else:
                        logger.error(f"下载视频失败，状态码: {response.status}")
                        return b""
        except Exception as e:
            logger.error(f"下载视频过程中发生异常: {str(e)}")
            return b""
    
    async def _download_image(self, image_url: str) -> bytes:
        """下载封面图片"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        logger.debug(f"下载的封面图片数据大小: {len(image_data)} bytes")
                        return image_data
                    else:
                        logger.error(f"下载封面图片失败，状态码: {response.status}")
                        return b""
        except Exception as e:
            logger.error(f"下载封面图片过程中发生异常: {str(e)}")
            return b""
    
    async def _check_task_result(self, bot: WechatAPIClient, from_wxid: str, sender_wxid: str, task_id: str):
        """异步检查任务结果，完成后下载并发送视频，使用返回的封面图片"""
        max_attempts = 60  # 最大检查次数（约10分钟）
        interval = 10  # 检查间隔（秒）
        
        for _ in range(max_attempts):
            result = await self._retrieve_video_result(task_id)
            if not result:
                await bot.send_at_message(from_wxid, f"\n任务 {task_id} 查询失败！", [sender_wxid])
                break
            
            status = result.task_status
            if status == "SUCCESS":
                video_url = result.video_result[0].url
                cover_url = result.video_result[0].cover_image_url
                
                # 下载视频和封面
                video_data = await self._download_video(video_url)
                cover_data = await self._download_image(cover_url)
                
                if video_data:
                    try:
                        video_base64 = base64.b64encode(video_data).decode("utf-8")
                        image_base64 = base64.b64encode(cover_data).decode("utf-8") if cover_data else None
                        await bot.send_video_message(from_wxid, video=video_base64, image=image_base64)
                        logger.info(f"成功发送视频到 {from_wxid}，封面: {cover_url if image_base64 else '无'}")
                    except Exception as e:
                        logger.error(f"发送视频失败: {str(e)}")
                        await bot.send_at_message(from_wxid, f"\n视频发送失败: {str(e)}", [sender_wxid])
                else:
                    await bot.send_at_message(
                        from_wxid, 
                        f"\n视频生成完成，但下载失败！\n视频URL: {video_url}\n封面URL: {cover_url}", 
                        [sender_wxid]
                    )
                break
            elif status == "FAIL":
                await bot.send_at_message(from_wxid, f"\n任务 {task_id} 生成失败！", [sender_wxid])
                break
            else:
                await asyncio.sleep(interval)
        else:
            await bot.send_at_message(from_wxid, f"\n任务 {task_id} 处理超时，请使用'#查询视频 {task_id}'手动检查！", [sender_wxid])
    
    def _cleanup_expired_conversations(self):
        """清理过期的会话"""
        current_time = time.time()
        expired_keys = []
        
        for key, timestamp in self.conversation_timestamps.items():
            if current_time - timestamp > self.conversation_expiry:
                expired_keys.append(key)
        
        for key in expired_keys:
            if key in self.conversations:
                del self.conversations[key]
            if key in self.conversation_timestamps:
                del self.conversation_timestamps[key]