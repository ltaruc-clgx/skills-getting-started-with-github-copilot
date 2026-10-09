from copy import deepcopy

import pytest


def test_root_redirects_to_activity_page(client):
    # Arrange
    url = "/"

    # Act
    response = client.get(url, follow_redirects=False)

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_root_redirect_serves_activity_page(client):
    # Arrange
    url = "/"

    # Act
    response = client.get(url, follow_redirects=True)

    # Assert
    assert response.status_code == 200
    assert response.url.path == "/static/index.html"
    assert response.headers["content-type"].startswith("text/html")
    assert "Mergington High School" in response.text


def test_get_activities_returns_all_details(client, isolated_activities):
    # Arrange
    expected = deepcopy(isolated_activities)
    required_fields = {"description", "schedule", "max_participants", "participants"}

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == expected
    assert all(required_fields <= details.keys() for details in response.json().values())
    assert all(isinstance(details["participants"], list) for details in response.json().values())
    assert any(details["participants"] for details in response.json().values())
    assert any(not details["participants"] for details in response.json().values())


def test_signup_adds_participant_without_changing_other_data(client):
    # Arrange
    activity_name = "Chess Club"
    email = "new.student+chess@mergington.edu"
    before = client.get("/activities").json()
    expected = deepcopy(before)
    expected[activity_name]["participants"].append(email)

    # Act
    response = client.post(f"/activities/{activity_name}/signup", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected
    participants = activities_response.json()[activity_name]["participants"]
    assert participants.count(email) == 1
    assert len(participants) == len(before[activity_name]["participants"]) + 1


def test_removal_unregisters_participant_without_changing_other_data(client):
    # Arrange
    activity_name = "Chess Club"
    before = client.get("/activities").json()
    email = before[activity_name]["participants"][0]
    expected = deepcopy(before)
    expected[activity_name]["participants"].remove(email)

    # Act
    response = client.delete(f"/activities/{activity_name}/participants", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {activity_name}"}
    assert activities_response.status_code == 200
    assert activities_response.json() == expected
    participants = activities_response.json()[activity_name]["participants"]
    assert email not in participants
    assert len(participants) == len(before[activity_name]["participants"]) - 1


@pytest.mark.parametrize(
    "method, path, email, status_code, detail",
    [
        pytest.param(
            "POST", "/activities/Chess Club/signup", "michael@mergington.edu", 400,
            "Student already signed up for this activity", id="duplicate-signup",
        ),
        pytest.param(
            "POST", "/activities/Unknown Activity/signup", "new@mergington.edu", 404,
            "Activity not found", id="signup-unknown-activity",
        ),
        pytest.param(
            "DELETE", "/activities/Chess Club/participants", "absent@mergington.edu", 404,
            "Student is not signed up for this activity", id="remove-missing-participant",
        ),
        pytest.param(
            "DELETE", "/activities/Unknown Activity/participants", "new@mergington.edu", 404,
            "Activity not found", id="remove-unknown-activity",
        ),
    ],
)
def test_invalid_mutation_preserves_state(
    client, isolated_activities, method, path, email, status_code, detail
):
    # Arrange
    before = deepcopy(isolated_activities)

    # Act
    response = client.request(method, path, params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert isolated_activities == before
    assert activities_response.status_code == 200
    assert activities_response.json() == before


@pytest.mark.parametrize(
    "method, path",
    [
        pytest.param("POST", "/activities/Chess Club/signup", id="signup"),
        pytest.param("DELETE", "/activities/Chess Club/participants", id="removal"),
    ],
)
def test_missing_email_returns_validation_error_without_mutation(
    client, isolated_activities, method, path
):
    # Arrange
    before = deepcopy(isolated_activities)

    # Act
    response = client.request(method, path)
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 422
    assert any(error["loc"] == ["query", "email"] for error in response.json()["detail"])
    assert isolated_activities == before
    assert activities_response.status_code == 200
    assert activities_response.json() == before


def test_repeated_removal_returns_not_found_without_further_mutation(client, isolated_activities):
    # Arrange
    activity_name = "Chess Club"
    email = isolated_activities[activity_name]["participants"][0]
    first_removal = client.delete(
        f"/activities/{activity_name}/participants", params={"email": email}
    )
    before = deepcopy(isolated_activities)

    # Act
    response = client.delete(f"/activities/{activity_name}/participants", params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert first_removal.status_code == 200
    assert response.status_code == 404
    assert response.json() == {"detail": "Student is not signed up for this activity"}
    assert isolated_activities == before
    assert activities_response.status_code == 200
    assert activities_response.json() == before


def test_participant_can_register_again_after_last_participant_is_removed(client):
    # Arrange
    activity_name = "Soccer Team"
    email = "returning.student@mergington.edu"
    before = client.get("/activities").json()
    expected_registered = deepcopy(before)
    expected_registered[activity_name]["participants"].append(email)
    signup_path = f"/activities/{activity_name}/signup"
    removal_path = f"/activities/{activity_name}/participants"

    # Act
    signup_response = client.post(signup_path, params={"email": email})
    registered_response = client.get("/activities")
    removal_response = client.delete(removal_path, params={"email": email})
    removed_response = client.get("/activities")
    second_signup_response = client.post(signup_path, params={"email": email})
    registered_again_response = client.get("/activities")

    # Assert
    assert before[activity_name]["participants"] == []
    assert signup_response.status_code == 200
    assert removal_response.status_code == 200
    assert second_signup_response.status_code == 200
    assert registered_response.status_code == 200
    assert registered_response.json() == expected_registered
    assert removed_response.status_code == 200
    assert removed_response.json() == before
    assert removed_response.json()[activity_name]["participants"] == []
    assert registered_again_response.status_code == 200
    assert registered_again_response.json() == expected_registered