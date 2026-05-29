package com.iptv.player

import android.os.Bundle
import androidx.preference.EditTextPreference
import androidx.preference.PreferenceFragmentCompat
import androidx.preference.PreferenceManager

class SettingsActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        supportFragmentManager.beginTransaction()
            .replace(android.R.id.content, SettingsFragment())
            .commit()
        supportActionBar?.setDisplayHomeAsUpEnabled(true)
        title = "设置"
    }
    
    class SettingsFragment : PreferenceFragmentCompat() {
        override fun onCreatePreferences(savedInstanceState: Bundle?, rootKey: String?) {
            setPreferencesFromResource(R.xml.preferences, rootKey)
            
            val editPref = findPreference<EditTextPreference>("m3u_url")
            val prefs = PreferenceManager.getDefaultSharedPreferences(context)
            val currentUrl = prefs.getString("m3u_url", "https://itv.19860519.xyz/output/tv.m3u")
            editPref?.summary = currentUrl
            editPref?.setOnPreferenceChangeListener { _, newValue ->
                editPref.summary = newValue.toString()
                true
            }
        }
    }
    
    override fun onSupportNavigateUp(): Boolean {
        onBackPressedDispatcher.onBackPressed()
        return true
    }
}
