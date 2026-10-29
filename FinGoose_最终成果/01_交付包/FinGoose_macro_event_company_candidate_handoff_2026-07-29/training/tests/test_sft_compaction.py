from test_sft_projector import complete_event

from fingoose_training.sft_projector import project_sft_samples


def test_normal_sized_structured_samples_do_not_need_hard_truncation():
    samples = project_sft_samples([complete_event()])

    assert all(
        "[内容已按训练长度上限截断]" not in message["content"]
        for sample in samples
        for message in sample["messages"]
    )
