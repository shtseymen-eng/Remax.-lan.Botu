from remax_bot.scan_queue import AUTO_SCAN_SOURCE_LABELS, AutoScanQueue


SOURCES={
    "MyRE/MAX ÇARŞI":"https://remax.test/carsi",
    "MyRE/MAX ÇARŞI 2":"https://remax.test/carsi-2",
    "Emlakjet ÇARŞI":"https://emlakjet.test/carsi",
    "Sahibinden ÇARŞI":"https://sahibinden.test/carsi",
}


def test_auto_scan_queue_keeps_supported_order_and_only_one_active_source():
    queue=AutoScanQueue(SOURCES)
    queue.start(["MyRE/MAX ÇARŞI","MyRE/MAX ÇARŞI 2","Emlakjet ÇARŞI"])

    assert queue.next_item() == ("MyRE/MAX ÇARŞI",SOURCES["MyRE/MAX ÇARŞI"])
    assert queue.next_item() is None

    queue.complete(success=True)
    assert queue.next_item() == ("MyRE/MAX ÇARŞI 2",SOURCES["MyRE/MAX ÇARŞI 2"])

    queue.complete(success=False)
    assert queue.next_item() == ("Emlakjet ÇARŞI",SOURCES["Emlakjet ÇARŞI"])
    queue.complete(success=True)
    assert queue.next_item() is None
    assert queue.finished


def test_auto_scan_queue_ignores_sahibinden_unknown_and_duplicate_labels():
    queue=AutoScanQueue(SOURCES)
    queue.start([
        "Sahibinden ÇARŞI","Bilinmeyen","Emlakjet ÇARŞI","Emlakjet ÇARŞI",
    ])

    assert AUTO_SCAN_SOURCE_LABELS == (
        "MyRE/MAX ÇARŞI","MyRE/MAX ÇARŞI 2","Emlakjet ÇARŞI"
    )
    assert queue.next_item() == ("Emlakjet ÇARŞI",SOURCES["Emlakjet ÇARŞI"])
    queue.complete(success=False)
    assert queue.finished
