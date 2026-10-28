def htmx(client, url):
    return client.get(url, headers={"HX-Request": "true"})


def test_home_lists_only_secondary_years(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Year 7" in r.text and "Year 10" in r.text
    assert "Year 5" not in r.text


def test_year_lists_programmes(client):
    r = client.get("/year/10")
    assert "Biology · Higher · AQA" in r.text


def test_programme_shows_units_and_choice_points(client):
    r = client.get("/programme/1")
    assert "Place value" in r.text
    assert "Pick a ratio unit" in r.text
    assert "Ratio A" in r.text and "Ratio B" in r.text


def test_unit_page(client):
    r = client.get("/unit/1?p=1")
    assert "Ordering decimals" in r.text
    assert "Read whole numbers" in r.text
    assert "underpins everything" in r.text
    assert "2 common mistakes" in r.text


def test_lesson_page_and_navigation(client):
    r = client.get("/lesson/1?u=1")
    assert "I can order decimals." in r.text
    assert "Compare digits from the left." in r.text
    assert "a number with a decimal point" in r.text
    assert "/lesson/2?u=1" in r.text  # next lesson


def test_missing_items_404(client):
    for url in ["/year/99", "/programme/99", "/unit/99", "/lesson/99", "/check/unit/99"]:
        assert client.get(url).status_code == 404, url


def test_search_matches_names_and_keywords_in_secondary_only(client):
    r = htmx(client, "/search?q=decimal")
    assert "Ordering decimals" in r.text
    assert "<html" not in r.text  # partial for htmx
    assert "Animal cells" in htmx(client, "/search?q=nucleus").text
    assert "Halves" not in htmx(client, "/search?q=halves").text


def test_check_true_false_flow(client):
    r = client.get("/check/lesson/1")
    assert "True or false?" in r.text
    assert "The more decimal places, the bigger the number." in r.text

    right = htmx(client, "/check/lesson/1/answer?i=0&choice=false")
    assert "Correct" in right.text and "Score 1/1" in right.text
    wrong = htmx(client, "/check/lesson/1/answer?i=0&choice=true")
    assert "Not quite" in wrong.text and "Score 0/1" in wrong.text
    assert "Compare place value columns." in right.text


def test_check_reveal_card_and_finish(client):
    card = htmx(client, "/check/unit/1?i=1&score=1&asked=1")
    assert "A common mistake" in card.text
    revealed = htmx(client, "/check/unit/1/answer?i=1&score=1&asked=1&choice=reveal")
    assert "Use a place value chart." in revealed.text
    done = htmx(client, "/check/unit/1?i=2&score=1&asked=1")
    assert "All done" in done.text and "1 out of 1" in done.text


def test_missing_database_shows_help(client, monkeypatch, tmp_path):
    monkeypatch.setenv("OAK_DB", str(tmp_path / "nope.sqlite"))
    r = client.get("/")
    assert "download_data.py" in r.text
