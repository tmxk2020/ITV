package com.iptv.player

import android.content.Context
import android.util.Log
import com.iptv.player.model.Channel
import com.iptv.player.model.ChannelGroup
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

object DataManager {
    private const val TAG = "DataManager"
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()
    
    var allChannels: List<Channel> = emptyList()
    var channelGroups: List<ChannelGroup> = emptyList()
    var currentChannelIndex = 0
    
    suspend fun loadChannels(context: Context): Boolean = withContext(Dispatchers.IO) {
        try {
            val txtUrl = BuildConfig.IPTV_TXT_URL
            val request = Request.Builder().url(txtUrl).build()
            val response = client.newCall(request).execute()
            
            if (!response.isSuccessful) {
                Log.e(TAG, "Failed to load: ${response.code}")
                return@withContext false
            }
            
            val content = response.body?.string() ?: return@withContext false
            val channels = parseTxtContent(content)
            
            allChannels = channels
            channelGroups = groupChannels(channels)
            
            Log.i(TAG, "Loaded ${channels.size} channels")
            return@withContext true
        } catch (e: Exception) {
            Log.e(TAG, "Error loading channels", e)
            return@withContext false
        }
    }
    
    private fun parseTxtContent(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        var currentGroup = ""
        
        content.lines().forEach { line ->
            val trimmed = line.trim()
            when {
                trimmed.startsWith("#") && !trimmed.startsWith("#EXT") -> {
                    currentGroup = trimmed.drop(1).trim()
                }
                trimmed.contains(",") && (trimmed.startsWith("http") || trimmed.contains("http")) -> {
                    // 格式: 频道名,URL
                    val lastComma = trimmed.lastIndexOf(',')
                    if (lastComma > 0) {
                        val name = trimmed.substring(0, lastComma).trim()
                        val url = trimmed.substring(lastComma + 1).trim()
                        if (url.startsWith("http")) {
                            channels.add(Channel(name, url, currentGroup))
                        }
                    }
                }
                trimmed.startsWith("http") -> {
                    // 只有URL，使用上一行注释作为名称
                    channels.add(Channel("频道${channels.size + 1}", trimmed, currentGroup))
                }
            }
        }
        
        return channels
    }
    
    private fun groupChannels(channels: List<Channel>): List<ChannelGroup> {
        val groupMap = mutableMapOf<String, MutableList<Channel>>()
        
        channels.forEach { channel ->
            val groupName = channel.group.ifEmpty { "其他" }
            groupMap.getOrPut(groupName) { mutableListOf() }.add(channel)
        }
        
        // 按指定顺序排序分组
        val order = listOf("央视", "卫视", "地方", "港澳台", "📺央视频道", "📡卫视频道", "☘️北京频道", "☘️上海频道", "☘️天津频道", "☘️重庆频道", "☘️广东频道", "☘️浙江频道", "☘️江苏频道", "其他")
        
        return groupMap.entries
            .sortedBy { (key, _) -> order.indexOfFirst { key.contains(it) }.let { if (it == -1) order.size else it } }
            .map { ChannelGroup(it.key, it.value) }
    }
    
    fun getNextChannel(currentUrl: String): Channel? {
        val currentIdx = allChannels.indexOfFirst { it.url == currentUrl }
        if (currentIdx >= 0 && currentIdx + 1 < allChannels.size) {
            return allChannels[currentIdx + 1]
        }
        return allChannels.firstOrNull()
    }
    
    fun getPreviousChannel(currentUrl: String): Channel? {
        val currentIdx = allChannels.indexOfFirst { it.url == currentUrl }
        if (currentIdx > 0) {
            return allChannels[currentIdx - 1]
        }
        return allChannels.lastOrNull()
    }
}
