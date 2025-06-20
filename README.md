# JiraSprintTracker
An interactive, self-hosted dashboard to visualize Jira sprint progress with burn-up charts, Earned Value (EV), and Planned Value (PV). This tool is designed to provide development teams and stakeholders with a clear, real-time view of sprint performance.


![Jira Sprint Dashboard Screenshot](https://i.imgur.com/oROAg20.png) 
## Features

* **Sprint Burn-Up Charts:** Track the progress of story points over time for each sprint.
* **EV/PV Analysis:** An "All Time" view that compares Earned Value against Planned Value to gauge long-term project performance.
* **User-Specific Filtering:** Filter the dashboard to see metrics for the entire team or individual members.

## Authored By

This project was created by **mythster** a.k.a Ashir Gowardhan

## Getting Started

### Prerequisites

* Python 3.x
* A Jira account with API access.

### Setup and Usage

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/mythster/mythster-JiraSprintTracker.git
    cd mythster-JiraSprintTracker
    ```

2.  **Install Dependencies:**
    Install the required Python libraries using pip:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Credentials:**
    Create a `.env` file in the root of the project directory and add your Jira credentials. This file is ignored by Git, so your credentials will remain private.

    ```env
    # .env
    JIRA_SERVER="[https://your-domain.atlassian.net](https://your-domain.atlassian.net)"
    JIRA_EMAIL="your-jira-email@example.com"
    API_TOKEN="YourJiraAPIToken"
    ```

4.  **Generate Sprint Data:**
    Run the `update.sh` script to fetch the latest data from Jira and generate the `data.json` file.

    ```bash
    chmod +x update.sh
    ./update.sh
    ```

5.  **View the Dashboard:**
    Open the `index.html` file in your web browser to see the dashboard.

## License

This project is licensed under the Apache 2.0  License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.