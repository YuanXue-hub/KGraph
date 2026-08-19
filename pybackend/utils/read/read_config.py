import json
import os


class ReadConfig:

    def read_config(self, model_name: str) -> dict:
        current_path = os.path.abspath(__file__)
        read_dir = os.path.dirname(current_path)
        utils_dir = os.path.dirname(read_dir)
        project_dir = os.path.dirname(utils_dir)
        config_path = os.path.join(project_dir, "config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config_json = json.load(f)
        return config_json.get(model_name, {})

    def read_prompt(self, prompt_name: str = None) -> str:
        """
        读取 prompt 模板
        :param prompt_name: prompt 名称，如 "intention_recognition"
        :return: 如果指定名称则返回对应的模板字符串，否则返回整个字典
        """
        current_path = os.path.abspath(__file__)
        read_dir = os.path.dirname(current_path)
        utils_dir = os.path.dirname(read_dir)
        project_dir = os.path.dirname(utils_dir)
        config_path = os.path.join(project_dir, "prompt.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config_json = json.load(f)

        if prompt_name:
            return config_json.get(prompt_name, "")
        return config_json


# 使用
if __name__ == '__main__':
    config = ReadConfig()

    # 直接获取模板字符串
    template = config.read_prompt("intention_recognition")

    # 替换用户查询
    user_query = "福建舰部署在哪里？"
    final_prompt = template.replace("{{query}}", user_query)

    print(final_prompt)