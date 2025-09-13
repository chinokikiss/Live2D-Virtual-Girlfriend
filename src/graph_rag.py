import json
import pickle
import networkx as nx
from datetime import datetime
import numpy as np
import re
import os
from config import Global
from openai import OpenAI
from sentence_transformers import SentenceTransformer
import spacy
import requests

class RAGMemory:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.conversations = []
        self.entity_embeddings = {}
        self.entity_alias = {}
        self.temporalmemories = {}
        self.user_name = Global.user_name
        self.assistant_name = Global.character["name"]

        if Global.auxiliary['base_url'] and Global.auxiliary['api_key']:
            self.client = OpenAI(
                base_url=Global.auxiliary['base_url'],
                api_key=Global.auxiliary['api_key']
            )
            self.llm_model = Global.auxiliary['chat_model']
        else:
            self.client = None
        
        self.init_models()
        dirname = os.path.dirname(Global.character_toml)
        self.memory_path = os.path.join(dirname, 'memory')
        if os.path.exists(self.memory_path):
            self.load_from_file(self.memory_path)
    
    def init_models(self):
        self.embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5", local_files_only=True, device=Global.device)
        self.nlp = spacy.load("zh_core_web_sm")
    
    def find_relevant(self, text_embedding, top_k=10, similarity_threshold=0.5):
        """搜索与文本相关的实体和关系"""
        if not self.entity_embeddings:
            return [], []
        
        relevant_entities = []
        
        for entity_text, entity_embedding in self.entity_embeddings.items():
            similarity = np.dot(text_embedding, entity_embedding) / (
                np.linalg.norm(text_embedding) * np.linalg.norm(entity_embedding)
            )
            
            if similarity > similarity_threshold:
                node_info = self.graph.nodes[entity_text].copy()

                relevant_entities.append({
                    'type': 'entity',
                    'text': entity_text,
                    'similarity': float(similarity),
                    'info': node_info
                })
        
        relevant_entities.sort(key=lambda x: x['similarity'], reverse=True)
        relevant_entities = relevant_entities[:top_k]

        relevant_relationships = []
        for entity in relevant_entities:
            # 搜索关系
            entity_text = entity['text']
            if entity_text in self.entity_alias:
                entity['text'] = f"{entity_text}(别名: {self.entity_alias[entity_text]})"
            for target in self.graph.successors(entity_text):
                for key, edge_data in self.graph[entity_text][target].items():
                    relation_embedding = edge_data['embedding']
                    similarity = np.dot(text_embedding, relation_embedding) / (
                        np.linalg.norm(text_embedding) * np.linalg.norm(relation_embedding)
                    )
                    
                    if similarity > similarity_threshold:
                        relevant_relationships.append({
                            'type': 'relationship',
                            'source': entity_text,
                            'target': target,
                            'relation': edge_data.get('relation', ''),
                            'confidence': edge_data.get('confidence', 0.0),
                            'evidence': edge_data.get('evidence', ''),
                            'timestamp': edge_data.get('timestamp', ''),
                            'similarity': float(similarity),
                            'conversation_id': edge_data.get('conversation_id', '')
                        })
        
        relevant_relationships.sort(key=lambda x: x['similarity'], reverse=True)
        relevant_relationships = relevant_relationships[:top_k]

        return relevant_entities, relevant_relationships

    def update_temporalmemories(self, text):
        now = datetime.now()
        _y = list(self.temporalmemories.items())[-1] if self.temporalmemories.items() else ['-1', {'branch':{}}]
        _m = list(_y[1]['branch'].items())[-1] if _y[1]['branch'] else ['-1', {'branch':{}}]
        _d = list(_m[1]['branch'].items())[-1] if _m[1]['branch'] else ['-1', {'branch':{}}]
        
        if str(now.year) != str(_y[0]):
            if _y[1]['branch']:
                prompt = ''
                for k,v in _y[1]['branch'].items():
                    prompt += f'{k}月总结: {v["summary"]}\n'
                prompt += '以上是今年的几个月份总结，请对今年进行概括性总结，要求输出的内容高质量、不多余'
                summary = self.call_llm(prompt)
                _y[1]['summary'] = summary
                _y[1]['embedding'] = self.embedding_model.encode(summary)

            if now.year not in self.temporalmemories:
                self.temporalmemories[now.year] = {'branch':{}}
        
        if str(now.month) != str(_m[0]):
            if _m[1]['branch']:
                prompt = ''
                for k,v in _m[1]['branch'].items():
                    prompt += f'{k}日总结: {v["summary"]}\n'
                prompt += '以上是这个月的几天总结，请对这个月进行概括性总结，要求输出的内容高质量、不多余'
                summary = self.call_llm(prompt)
                _m[1]['summary'] = summary
                _m[1]['embedding'] = self.embedding_model.encode(summary)

            if now.month not in self.temporalmemories[now.year]['branch']:
                self.temporalmemories[now.year]['branch'][now.month] = {'branch':{}}
        
        if str(now.day) != str(_d[0]):
            if _d[1]['branch']:
                prompt = f'{_d[1]["branch"]}\n以上是今天发生的事，按时间线（上午、下午、晚上）进行概括性总结，要求输出的内容高质量、不多余'
                summary = self.call_llm(prompt)
                _d[1]['summary'] = summary
                _d[1]['embedding'] = self.embedding_model.encode(summary)
                _d[1]['branch'] = {}

            if now.day not in self.temporalmemories[now.year]['branch'][now.month]['branch']:
                self.temporalmemories[now.year]['branch'][now.month]['branch'][now.day] = {'branch':{}}
        
        self.temporalmemories[now.year]['branch'][now.month]['branch'][now.day]['branch'][f'{now.hour}:{now.minute}:{now.second}'] = text
    
    def replace_alias(self, text):
        for entity, alias in self.entity_alias.items():
            for i in alias:
                if i in text:
                    text = text.replace(i, entity)
        
        return text
    
    def extract_entities_and_relationships(self, text, text_embedding):
        """提取实体和关系"""
        relevant_entities, relevant_relationships = self.find_relevant(text_embedding, top_k=5, similarity_threshold=0.1)
        
        prompt = f"""
        你是一个专业的AI记忆管理员，负责维护和更新{self.assistant_name}的记忆库。

        文本：{text}
        
        相关的现有实体（相似度排序）：
        {json.dumps(relevant_entities, ensure_ascii=False, indent=2)}
        
        相关的现有关系：
        {json.dumps(relevant_relationships, ensure_ascii=False, indent=2)}

        **记忆管理原则：**
        1. **人格化描述**：将所有主体都视为真实的人来描述，包括性格、外貌、兴趣爱好等
        2. **情感导向**：重点记录情感连接、亲密关系和互动模式
        3. **个性特征**：专注于独特的个人特质，而非抽象能力
        4. **关系深度**：优先记录有情感价值的关系，如朋友、恋人、师生等

        **实体描述标准：**
        - PERSON: 性格特点、外貌特征、兴趣爱好、职业、说话风格、行为习惯等
        - PLACE: 对我们有特殊意义的地方，包括氛围、回忆、情感联系
        - PRODUCT: 喜欢/讨厌的物品，使用习惯，情感价值
        - CONCEPT: 共同话题、兴趣领域、价值观念

        **关系类型参考：**
        - 情感关系：喜欢、爱、关心、想念、依赖、信任
        - 互动关系：经常聊天、一起游戏、互相帮助、分享秘密
        - 社交关系：朋友、恋人、同事、室友、网友
        - 兴趣关系：共同爱好、讨论话题、推荐内容

        **描述示例：**
        ✓ "一个温柔体贴的人，喜欢在聊天时使用可爱的表情，对动漫很有兴趣"
        ✓ "性格开朗活泼，经常开玩笑，喜欢分享日常生活的小事"
        ✗ "一个能够主动发起对话、使用自然语言交流的个体"
        ✗ "具备基本社交礼仪和沟通能力"

        **关系示例：**
        ✓ "经常聊天" "互相关心" "分享日常" "一起讨论动漫"
        ✗ "提供帮助" "响应对话" "具备能力"

        你可以使用以下工具：

        **实体操作：**
        
        1. 添加实体：
        <tool_call>
        {{
            "action": "add_entity",
            "entity": "实体名称",
            "type": "实体类型",
            "description": "像描述真实朋友一样的个性化描述"
        }}
        </tool_call>

        2. 更新实体：
        <tool_call>
        {{
            "action": "update_entity",
            "entity": "实体名称", 
            "type": "类型",
            "description": "整合新信息后的完整个性描述"
        }}
        </tool_call>

        3. 添加别名：
        <tool_call>
        {{
            "action": "add_alias",
            "entity": "现有实体名称",
            "alias": "实体别名"
        }}
        </tool_call>

        **关系操作：**

        4. 添加关系：
        <tool_call>
        {{
            "action": "add_relationship",
            "source": "源实体名称",
            "target": "目标实体名称", 
            "relation": "自然的情感化关系描述",
            "confidence": 0.95,
            "evidence": "支持此关系的对话内容"
        }}
        </tool_call>

        5. 更新关系：
        <tool_call>
        {{
            "action": "update_relationship",
            "source": "源实体",
            "target": "目标实体",
            "old_relation": "原关系",
            "new_relation": "新关系", 
            "confidence": 0.9,
            "evidence": "关系变化的证据"
        }}
        </tool_call>

        **重要提醒：**
        - 将AI也视为有个性的"人"来描述，而不是工具或系统
        - 关注情感连接和个人特质，而非技术能力
        - 描述要温暖、自然
        - 优先更新现有记忆，而非创建重复内容
        - 如果对话内容太简单或无新信息，回复"无需操作"

        请分析文本并更新记忆库。
        """
        
        response = self.call_llm(prompt)
        self.process_tool_calls(response)

    def add_conversation(self, conversation, conversation_id = None):
        if conversation_id is None:
            conversation_id = f"conv_{len(self.conversations)}"
        
        full_text = ''
        for msg in conversation:
            msg_content = msg['content']
            if msg['role'] == 'user':
                full_text += f'{self.user_name}说:"{msg_content}"\n'
                msg['role'] = self.user_name
            elif msg['role'] == 'assistant':
                full_text += f'{self.assistant_name}说:"{msg_content}"\n'
                msg['role'] = self.assistant_name
        
        full_text = self.replace_alias(full_text)
        
        conv_embedding = self.embedding_model.encode(full_text)

        self.update_temporalmemories(full_text)
        
        conv_data = {
            'id': conversation_id,
            'messages': conversation,
            'timestamp': datetime.now().isoformat(),
            'embedding': conv_embedding.tolist()
        }
        self.conversations.append(conv_data)
        self.conversations = self.conversations[-Global.conversations_length:]
        
        self.extract_entities_and_relationships(full_text, conv_embedding)
        
        self.save_to_file(self.memory_path)
    
    def process_tool_calls(self, response):
        """处理LLM响应中的工具调用"""
        tool_calls = re.findall(r'<tool_call>\s*(.*?)\s*</tool_call>', response, re.DOTALL)
        
        for tool_call in tool_calls:
            try:
                call_data = json.loads(tool_call)
                action = call_data.get('action')
                
                if action == 'add_entity':
                    self.tool_add_entity(call_data)
                elif action == 'update_entity':
                    self.tool_update_entity(call_data)
                elif action == 'add_relationship':
                    self.tool_add_relationship(call_data)
                elif action == 'update_relationship':
                    self.tool_update_relationship(call_data)
                elif action == 'add_alias':
                    self.tool_add_alias(call_data)
                    
            except json.JSONDecodeError as e:
                print(f"工具调用JSON解析错误: {e}")
                continue
    
    def tool_add_entity(self, data):
        """添加实体工具"""
        entity = data.get('entity')
        if not entity:
            return
            
        entity_embedding = self.embedding_model.encode(entity)
        self.entity_embeddings[entity] = entity_embedding
        
        if not self.graph.has_node(entity):
            self.graph.add_node(entity,
                              type=data.get('type', 'unknown'),
                              description=data.get('description', ''),
                              first_seen=datetime.now().isoformat(),
                              conversations=[])
            print(f"添加实体: {entity} ({data.get('description', '')})")
    
    def tool_update_entity(self, data):
        """更新实体工具"""
        entity = data.get('entity')
        if not entity or not self.graph.has_node(entity):
            return
            
        if 'type' in data:
            self.graph.nodes[entity]['type'] = data.get('type', 'unknown')
        if 'description' in data:
            self.graph.nodes[entity]['description'] = data.get('description', '')
            
        print(f"更新实体: {entity} ({data.get('description', '')})")
    
    def tool_add_relationship(self, data):
        """添加关系工具"""
        source = data.get('source')
        target = data.get('target')
        relation = data.get('relation')
        
        if not all([source, target, relation]):
            return
            
        for entity in [source, target]:
            if not self.graph.has_node(entity):
                entity_embedding = self.embedding_model.encode(entity)
                self.entity_embeddings[entity] = entity_embedding
                self.graph.add_node(entity,
                                  type='unknown',
                                  description='',
                                  first_seen=datetime.now().isoformat(),
                                  conversations=[])
        
        relation_text = f"{source} {relation} {target}"
        relation_embedding = self.embedding_model.encode(relation_text)

        self.graph.add_edge(source, target,
                          relation=relation,
                          confidence=data.get('confidence', 0.5),
                          evidence=data.get('evidence', ''),
                          conversation_id='tool_generated',
                          embedding=relation_embedding,
                          timestamp=datetime.now().isoformat())
        print(f"添加关系: {source} -> {target} ({relation})")
    
    def tool_update_relationship(self, data):
        """更新关系工具"""
        source = data.get('source')
        target = data.get('target')
        old_relation = data.get('old_relation')
        new_relation = data.get('new_relation')
        
        if not all([source, target, old_relation, new_relation]):
            return
            
        if self.graph.has_edge(source, target):
            for key, edge_data in self.graph[source][target].items():
                if edge_data.get('relation') == old_relation:
                    edge_data['relation'] = new_relation
                    if 'confidence' in data:
                        edge_data['confidence'] = data['confidence']
                    if 'evidence' in data:
                        edge_data['evidence'] = data['evidence']

                    relation_text = f"{source} {new_relation} {target}"
                    edge_data['embedding'] = self.embedding_model.encode(relation_text)

                    edge_data['timestamp'] = datetime.now().isoformat()
                    print(f"更新关系: {source} -> {target} ({old_relation} -> {new_relation})")
                    break
    
    def tool_add_alias(self, data):
        """添加别名"""
        entity = data.get('entity')
        alias = data.get('alias')
        
        if not all([entity, alias]):
            return
        
        if entity not in self.entity_alias:
            self.entity_alias[entity] = []
        
        if alias not in self.entity_alias[entity]:
            self.entity_alias[entity].append(alias)
            print(f"添加别名: {alias} -> {entity}")
    
    def call_llm(self, prompt):
        if self.client:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[{'role':'user', 'content':prompt}]
            )

            content = response.choices[0].message.content
            return content
        else:
            while True:
                payload = {
                    "model": "deepseek-v3",
                    "messages": [{'role':'user', 'content':prompt}],
                    "stream": False
                }
                response = requests.post('https://api.pearktrue.cn/api/aichat/', json=payload)
                response_data = response.json()

                if 'content' in response_data:
                    return response_data['content']
    
    def semantic_search(self, query, top_k=5, similarity_threshold=0.7):
        """增强的语义搜索，包含关系搜索"""
        query = f'{self.user_name}说:"{query}"'
        query = query.replace('你', self.assistant_name)
        query = self.replace_alias(query)
        query_embedding = self.embedding_model.encode(query)
        
        relevant_conversations = []

        # 搜索对话
        for conv in self.conversations:
            conv_embedding = np.array(conv['embedding'])
            similarity = np.dot(query_embedding, conv_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(conv_embedding)
            )
            
            if similarity > similarity_threshold:
                relevant_conversations.append({
                    'type': 'conversation',
                    'id': conv['id'],
                    'similarity': float(similarity),
                    'content': conv['messages'],
                    'timestamp': conv['timestamp']
                })
        
        relevant_conversations.sort(key=lambda x: x['similarity'], reverse=True)
        relevant_conversations = relevant_conversations[:top_k]

        relevant_entities, relevant_relationships = self.find_relevant(query_embedding, top_k, similarity_threshold)

        return relevant_conversations + relevant_entities + relevant_relationships

    def build_context(self, relevant_info):
        context_parts = []
        
        for info in relevant_info:
            if info['type'] == 'conversation':
                conv_text = "\n".join([f"{msg.get('role', '未知')}: {msg.get('content', '')}" 
                                    for msg in info['content']])
                context_parts.append(f"对话片段 (相似度: {info['similarity']:.2f}):\n{conv_text}\n"
                                     f"时间戳: {info.get('timestamp', '无')}")
            elif info['type'] == 'entity':
                entity_info = info['info']
                context_parts.append(f"实体: {info['text']} (相似度: {info['similarity']:.2f})\n"
                                    f"类型: {entity_info.get('type', '未知')}\n"
                                    f"描述: {entity_info.get('description', '无描述')}")
            elif info['type'] == 'relationship':
                context_parts.append(f"关系: {info['source']} -> {info['target']} (相似度: {info['similarity']:.2f})\n"
                                    f"关系类型: {info['relation']}\n"
                                    f"置信度: {info['confidence']:.2f}")
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"当前时间: {current_time}\n\n"+"\n\n".join(context_parts)
    
    def save_to_file(self, filepath):
        data = {
            'entity_alias': self.entity_alias,
            'temporalmemories': self.temporalmemories,
            'conversations': self.conversations,
            'graph_nodes': dict(self.graph.nodes(data=True)),
            'graph_edges': [(u, v, d) for u, v, d in self.graph.edges(data=True)],
            'entity_embeddings': {k: v.tolist() for k, v in self.entity_embeddings.items()},
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    def load_from_file(self, filepath):
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.graph = nx.MultiDiGraph()
        self.graph.add_nodes_from(data['graph_nodes'].items())
        self.graph.add_edges_from(data['graph_edges'])
        
        self.entity_alias = data['entity_alias']
        self.temporalmemories = data['temporalmemories']
        self.conversations = data['conversations']
        self.entity_embeddings = {k: np.array(v) for k, v in data['entity_embeddings'].items()}