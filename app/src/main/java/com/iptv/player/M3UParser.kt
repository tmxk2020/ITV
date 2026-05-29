package com.iptv.player

import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.BufferedReader
import java.io.StringReader
import java.util.concurrent.TimeUnit

object M3UParser {
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    suspend fun fetchAndParse(url: String): List<Channel> {
        val request = Request.Builder().url(url).build()
        val response = client.newCall(request).execute()
        if (!response.isSuccessful) throw Exception("HTTP ${response.code}")
        val content = response.body?.string() ?: ""
        return parse(content)
    }

    fun parse(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        val reader = BufferedReader(StringReader(content))
        var line: String?
        var currentExtinf: String? = null

        while (reader.readLine().also { line = it } != null) {
            val l = line!!
            if (l.startsWith("#EXTINF")) {
                currentExtinf = l
            } else if (l.startsWith("http://") || l.startsWith("https://") || l.startsWith("rtmp://")) {
                if (currentExtinf != null) {
                    val channel = parseExtinf(currentExtinf, l)
                    channels.add(channel)
                    currentExtinf = null
                }
            }
        }
        return channels
    }

    private fun parseExtinf(extinfLine: String, url: String): Channel {
        var name = ""
        var group = ""
        var tvgId = ""
        var tvgLogo = ""

        val commaIndex = extinfLine.lastIndexOf(',')
        if (commaIndex != -1 && commaIndex + 1 < extinfLine.length) {
            name = extinfLine.substring(commaIndex + 1).trim()
        }

        val tvgIdPattern = Regex("""tvg-id="([^"]*)""")
        val tvgLogoPattern = Regex("""tvg-logo="([^"]*)""")
        val groupPattern = Regex("""group-title="([^"]*)""")

        tvgIdPattern.find(extinfLine)?.let { tvgId = it.groupValues[1] }
        tvgLogoPattern.find(extinfLine)?.let { tvgLogo = it.groupValues[1] }
        groupPattern.find(extinfLine)?.let { group = it.groupValues[1] }

        return Channel(name, url, group, tvgId, tvgLogo)
    }
}
