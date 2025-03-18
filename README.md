# 🎬 CogVideoX 视频生成器

> 🚀 使用智谱 AI 最先进的 CogVideoX 模型生成高质量视频！
> **本插件是 [XYBotv2](https://github.com/HenryXiaoYang/XYBotv2) 的一个插件。**

<img src="https://github.com/user-attachments/assets/a2627960-69d8-400d-903c-309dbeadf125" width="400" height="600">

## ✨ 功能特点

- 🖋️ **文本生成视频** - 通过文字描述生成高质量视频
- 🖼️ **图片生成视频** - 基于上传的图片生成相关视频
- 🔍 **任务查询** - 查询视频生成任务的状态和结果
- 📐 **自定义参数** - 支持自定义视频分辨率和比例
- 💰 **积分系统** - 集成积分消费功能
- 🎞️ **自动下载** - 视频生成完成后自动下载并发送
- 🖼️ **封面支持** - 自动提取并使用视频封面
- ⏱️ **会话管理** - 自动清理过期会话，提高资源利用率

## 🛠️ 依赖要求与安装

### 必要依赖

- Python 3.11+
- 以下 Python 库:
  - `zhipuai`: 智谱 AI 官方 SDK
  - `loguru`: 日志记录
  - `aiohttp`: 异步 HTTP 客户端
  - `tomllib`: Python 3.11+ 内置库，用于解析 TOML 配置文件

### 安装方法

1. 确保您已安装 Python 3.11 或更高版本
2. 使用 pip 安装所需依赖:

```bash
# 安装智谱AI官方SDK
pip install zhipuai

# 安装其他依赖
pip install loguru aiohttp
```

3. 将插件文件夹放入 XYBotv2 的 `_data/plugins/` 目录中
4. 创建 `config.toml` 配置文件并填写相关配置
5. 重启 XYBotv2 以加载插件

## 📋 使用指南

### 文本生成视频命令

使用以下命令从文本生成视频：

```
#生成视频 [描述] [--size 宽度x高度] [--ratio 宽:高]
```

### 图片生成视频命令

上传图片并添加以下描述：

```
#图生视频 [描述] [--size 宽度x高度] [--ratio 宽:高]
```

### 查询视频任务

```
#查询视频 [任务ID]
```

### 结束对话命令

```
#结束对话
#退出对话
```

### 🔄 参数说明

- **描述**：对要生成视频的详细描述
- **--size**：可选参数，指定视频分辨率，如 `1920x1080`
- **--ratio**：可选参数，指定视频比例，如 `16:9`

## 💎 示例提示词

### 文本生成视频

- `#生成视频 海浪拍打沙滩，阳光明媚，海鸥飞过`
- `#生成视频 繁华的城市夜景，霓虹灯闪烁，车流如织 --size 1280x720`
- `#生成视频 森林中的小溪，阳光透过树叶，水面波光粼粼 --ratio 9:16`

### 图片生成视频

- `#图生视频 让图片中的场景动起来，增加流动的云彩`
- `#图生视频 为静态图片添加动态效果，人物开始行走 --size 1280x720`

## ⚙️ 配置说明

在`config.toml`中设置：

```toml
[CogVideoX]
# 基本配置
enable = true
api_key = "您的智谱AI API密钥"
model = "cogvideox-2"

# 命令配置
generate_commands = ["#生成视频"]
image_generate_commands = ["#图生视频"]
query_commands = ["#查询视频"]
exit_commands = ["#结束对话", "#退出对话"]

# 积分配置
enable_points = true
generate_cost = 20

# 视频保存配置
save_path = "temp"

# 默认分辨率和比例
default_size = "1920x1080"
default_ratio = "16:9"

# 管理员列表（不消耗积分）
admins = []
```

## 📊 积分系统

- 生成视频：消耗 20 积分
- 管理员可免费使用
- 可在配置文件中调整积分消耗量

## 📢 注意事项

- 视频生成需要一定时间，请耐心等待
- 生成视频会消耗积分，请确保积分充足
- 管理员用户不消耗积分
- 会话在一小时无活动后自动过期
- 需要有效的智谱 AI API 密钥，可在[智谱 AI 官网](https://open.bigmodel.cn/)申请

## 📝 开发日志

- v1.0.0: 初始版本发布
- v1.1.0: 添加自定义分辨率和比例功能、优化视频下载和发送逻辑、添加封面图片支持

## 👨‍💻 作者

**老夏的金库** ©️ 2024

**给个 ⭐ Star 支持吧！** 😊

**开源不易，感谢打赏支持！**

![image](https://github.com/user-attachments/assets/2dde3b46-85a1-4f22-8a54-3928ef59b85f)

## �� 许可证

MIT License
