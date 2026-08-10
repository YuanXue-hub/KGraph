package com.yuan.seedboot.service.Impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.yuan.seedboot.model.entity.ChatHistory;
import com.yuan.seedboot.service.ChatHistoryService;
import com.yuan.seedboot.mapper.ChatHistoryMapper;
import org.springframework.stereotype.Service;

/**
* @author Yuan
* @description 针对表【chat_history(对话历史)】的数据库操作Service实现
* @createDate 2026-06-14 21:25:16
*/
@Service
public class ChatHistoryServiceImpl extends ServiceImpl<ChatHistoryMapper, ChatHistory>
    implements ChatHistoryService{

}




