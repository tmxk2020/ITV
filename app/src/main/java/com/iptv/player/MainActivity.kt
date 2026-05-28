package com.iptv.player

import android.os.Bundle
import android.view.View
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.SimpleExoPlayer
import com.google.android.exoplayer2.source.hls.HlsMediaSource
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector
import com.google.android.exoplayer2.ui.PlayerView
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.URLEncoder
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var playerView: PlayerView
    private lateinit var loadingSpinner: ProgressBar
    private lateinit var errorText: TextView
    private lateinit var channelList: RecyclerView
    private var exoPlayer: SimpleExoPlayer? = null
    private var currentChannelUrl: String? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
        .build()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        playerView = findViewById(R.id.player_view)
        loadingSpinner = findViewById(R.id.loading_spinner)
        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)

        channelList.layoutManager = LinearLayoutManager(this)

        // 获取基础 URL（不包含文件名）
        val baseUrl = BuildConfig.BASE_URL
        // 移除可能的文件名，只保留目录路径
        val baseDir = if (baseUrl.contains("/output/")) {
            baseUrl.substringBeforeLast("/output/") + "/output/"
        } else if (baseUrl.contains("/")) {
            baseUrl.substringBeforeLast("/") + "/"
        } else {
            baseUrl
        }
        
        // 优先尝试 M3U，失败则尝试 TXT
        loadPlaylistWithFallback(baseDir)
    }

    private fun loadPlaylistWithFallback(baseDir: String) {
        // 先尝试加载 .m3u 文件
        loadChannelList("${baseDir}tv.m3u", isM3uFormat = true) { success ->
            if (!success) {
                // .m3u 失败，尝试 .txt 文件
                println("M3U 加载失败，尝试 TXT 格式...")
                loadChannelList("${baseDir}tv.txt", isM3uFormat = false) { txtSuccess ->
                    if (!txtSuccess) {
                        runOnUiThread {
                            loadingSpinner.visibility = View.GONE
                            errorText.text = "无法加载播放列表\n请检查网络或源地址"
                            errorText.visibility = View.VISIBLE
                            Toast.makeText(this, "M3U 和 TXT 格式均加载失败", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    private fun loadChannelList(playlistUrl: String, isM3uFormat: Boolean, onResult: (Boolean) -> Unit) {
        runOnUiThread {
            loadingSpinner.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }
        
        println("=== IPTV Debug ===")
        println("尝试加载: $playlistUrl")
        println("格式类型: ${if (isM3uFormat) "M3U" else "TXT"}")

        thread {
            try {
                val request = Request.Builder().url(playlistUrl).build()
                val response = client.newCall(request).execute()
                println("HTTP 状态码: ${response.code}")
                
                if (!response.isSuccessful) {
                    onResult(false)
                    return@thread
                }
                
                val content = response.body?.string() ?: ""
                println("下载内容长度: ${content.length} 字符")
                
                val channels = if (isM3uFormat) {
                    parseM3uPlaylist(content)
                } else {
                    parseTxtPlaylist(content)
                }
                
                println("解析到频道数量: ${channels.size}")
                
                if (channels.isEmpty()) {
                    onResult(false)
                    return@thread
                }
                
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    setupChannelList(channels)
                    if (channels.isNotEmpty()) {
                        println("尝试播放第一个频道: ${channels[0].name} - ${channels[0].url}")
                        playChannel(channels[0].url)
                    }
                }
                onResult(true)
            } catch (e: Exception) {
                e.printStackTrace()
                println("加载失败: ${e.message}")
                onResult(false)
            }
        }
    }

    // 解析 M3U 格式
    private fun parseM3uPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        var currentName = ""
        
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) continue
            
            if (trimmed.startsWith("#EXTINF")) {
                // 提取频道名
                val nameStart = trimmed.lastIndexOf(",")
                if (nameStart != -1) {
                    currentName = trimmed.substring(nameStart + 1).trim()
                }
            } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                // URL 行
                if (currentName.isNotEmpty()) {
                    channels.add(Channel(currentName, trimmed))
                    currentName = ""
                }
            }
        }
        
        return channels
    }

    // 解析 TXT 格式（频道名,URL）
    private fun parseTxtPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) continue
            val commaIndex = trimmed.indexOf(',')
            if (commaIndex > 0) {
                val name = trimmed.substring(0, commaIndex)
                val url = trimmed.substring(commaIndex + 1)
                if (url.startsWith("http")) {
                    channels.add(Channel(name, url))
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = ChannelAdapter(channels) { channel ->
            playChannel(channel.url)
        }
        channelList.adapter = adapter
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url

        releasePlayer()
        val trackSelector =        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)

        channelList.layoutManager = LinearLayoutManager(this)

        // 直接使用构建时写入的地址
        loadChannelList(BuildConfig.BASE_URL)
    }

    private fun loadChannelList(playlistUrl: String) {
        loadingSpinner.visibility = View.VISIBLE
        errorText.visibility = View.GONE

        thread {
            try {
                val request = Request.Builder().url(playlistUrl).build()
                val response = client.newCall(request).execute()
                if (!response.isSuccessful) {
                    throw Exception("HTTP ${response.code}")
                }
                val content = response.body?.string() ?: ""
                val channels = parseTxtPlaylist(content)
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    if (channels.isEmpty()) {
                        errorText.text = "未找到任何频道，请检查网络或源地址"
                        errorText.visibility = View.VISIBLE
                    } else {
                        setupChannelList(channels)
                        // 默认播放第一个频道
                        if (channels.isNotEmpty()) {
                            playChannel(channels[0].url)
                        }
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    errorText.text = "加载频道列表失败: ${e.message}"
                    errorText.visibility = View.VISIBLE
                }
            }
        }
    }

    // 解析 TV.TXT 格式 (频道名,URL)
    private fun parseTxtPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) continue
            val commaIndex = trimmed.indexOf(',')
            if (commaIndex > 0) {
                val name = trimmed.substring(0, commaIndex)
                val url = trimmed.substring(commaIndex + 1)
                if (url.startsWith("http")) {
                    channels.add(Channel(name, url))
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = ChannelAdapter(channels) { channel ->
            playChannel(channel.url)
        }
        channelList.adapter = adapter
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url

        releasePlayer()
        val trackSelector = DefaultTrackSelector(this)
        exoPlayer = SimpleExoPlayer.Builder(this).setTrackSelector(trackSelector).build()
        playerView.player = exoPlayer

        val dataSourceFactory = DefaultHttpDataSource.Factory()
        // HLS 流媒体源处理
        val mediaSource = HlsMediaSource.Factory(dataSourceFactory)
            .createMediaSource(MediaItem.fromUri(url))
        exoPlayer?.setMediaSource(mediaSource)
        exoPlayer?.prepare()
        exoPlayer?.playWhenReady = true
    }

    private fun releasePlayer() {
        exoPlayer?.release()
        exoPlayer = null
        playerView.player = null
    }

    override fun onDestroy() {
        super.onDestroy()
        releasePlayer()
    }

    data class Channel(val name: String, val url: String)
}
