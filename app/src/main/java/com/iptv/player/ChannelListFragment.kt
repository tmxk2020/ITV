package com.iptv.player

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.iptv.player.model.Channel
import com.iptv.player.model.ChannelGroup

class ChannelListFragment : Fragment() {

    private var _binding: View? = null
    private val binding get() = _binding!!
    private var recyclerView: RecyclerView? = null
    private lateinit var groupContainer: LinearLayout
    private var onChannelSelectedListener: ((Channel, Int) -> Unit)? = null
    private var currentGroupAdapter: ChannelAdapter? = null
    private var currentGroupChannels: List<Channel> = emptyList()
    private var selectedPosition = -1
    private var groupButtons = mutableListOf<View>()
    private var isViewCreated = false

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = inflater.inflate(R.layout.fragment_channel_list, container, false)
        return binding
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        recyclerView = view.findViewById(R.id.channel_recycler_view)
        groupContainer = view.findViewById(R.id.group_container)
        recyclerView?.layoutManager = LinearLayoutManager(context)
        setupGroupButtons()
        isViewCreated = true
    }

    private fun setupGroupButtons() {
        groupContainer.removeAllViews()
        groupButtons.clear()

        DataManager.channelGroups.forEachIndexed { index, group ->
            val button = android.widget.Button(requireContext()).apply {
                text = group.name.take(8)
                tag = index
                setBackgroundResource(android.R.drawable.btn_default)
                setPadding(40, 20, 40, 20)
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply {
                    setMargins(10, 5, 10, 5)
                }
                setOnClickListener {
                    selectGroup(index)
                }
            }
            groupContainer.addView(button)
            groupButtons.add(button)
        }

        if (DataManager.channelGroups.isNotEmpty()) {
            selectGroup(0)
        }
    }

    private fun selectGroup(index: Int) {
        if (recyclerView == null) return
        currentGroupChannels = DataManager.channelGroups[index].channels
        currentGroupAdapter = ChannelAdapter(currentGroupChannels) { channel, position ->
            selectedPosition = position
            onChannelSelectedListener?.invoke(channel, position)
            hide()
        }
        recyclerView?.adapter = currentGroupAdapter
        currentGroupAdapter?.setSelectedPosition(selectedPosition)

        groupButtons.forEachIndexed { i, button ->
            button.isSelected = i == index
        }
    }

    fun setOnChannelSelectedListener(listener: (Channel, Int) -> Unit) {
        onChannelSelectedListener = listener
    }

    fun updateSelectedPosition(position: Int) {
        selectedPosition = position
        currentGroupAdapter?.setSelectedPosition(position)
        if (position >= 0) {
            recyclerView?.scrollToPosition(position)
        }
    }

    fun show() {
        view?.visibility = View.VISIBLE
    }

    fun hide() {
        view?.visibility = View.GONE
    }

    fun isListVisible(): Boolean {
        return isViewCreated && view?.visibility == View.VISIBLE
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
        recyclerView = null
        isViewCreated = false
    }
}
