// File: apps/education_extras/education_extras/public/js/workspace_scripts.js

$(document).ready(function() {
    console.log("Custom App 'education_extras' - workspace_scripts.js - Document Ready. Current Path:", window.location.pathname);

    if (window.location.pathname === "/app/education" || window.location.pathname.startsWith("/app/education/")) {
        console.log("ON EDUCATION WORKSPACE PAGE (/app/education) - via custom app script.");

        if (typeof frappe !== 'undefined' && frappe.user_roles) {
            const userRoles = frappe.user_roles;
            const isInstructor = userRoles.includes("Instructor");
            const isSystemManager = userRoles.includes("System Manager");

            console.log("User Roles:", userRoles);
            console.log("Is user an Instructor?", isInstructor);
            console.log("Is user a System Manager?", isSystemManager);

            // Define the cards to hide
            const cardsToHideSelectors = {
                "Other Reports": 'div[card_name="Other Reports"]',
                "Settings": 'div[card_name="Settings"]',
                "Content Masters": 'div[card_name="Content Masters"]' // <<< ADDED THIS CARD
            };
            const cardNamesToHide = Object.keys(cardsToHideSelectors);
            const totalCardsToHide = cardNamesToHide.length;

            if (isInstructor && !isSystemManager) {
                console.log(`User is an Instructor AND NOT a System Manager. Will attempt to hide ${totalCardsToHide} cards on /app/education.`);

                function hideCard(cardName, selector, attemptType) {
                    let cardElement = $(selector);
                    console.log(`  [${attemptType}] '${cardName}' card selector matched: ${cardElement.length}`);
                    if (cardElement.length > 0) {
                        if (cardElement.css('display') !== 'none') {
                            cardElement.css('display', 'none');
                            console.log(`  [${attemptType}] '${cardName}' card hidden.`);
                            return true; // Card was found and actioned (hidden)
                        } else {
                            console.log(`  [${attemptType}] '${cardName}' card ALREADY hidden.`);
                            return true; // Card was found (already hidden)
                        }
                    }
                    return false; // Card not found
                }

                function processCards(attemptType = 'Initial') {
                    console.log(`processCards - Attempt Type: ${attemptType}`);
                    let cardsProcessedThisAttempt = 0;
                    for (const cardName of cardNamesToHide) {
                        if (hideCard(cardName, cardsToHideSelectors[cardName], attemptType)) {
                            cardsProcessedThisAttempt++;
                        }
                    }
                    console.log(`processCards - Attempt Type: ${attemptType} - Processed this round: ${cardsProcessedThisAttempt}`);
                    return cardsProcessedThisAttempt;
                }

                function countCurrentlyHiddenCards() {
                    let count = 0;
                    for (const cardName of cardNamesToHide) {
                        if ($(cardsToHideSelectors[cardName] + ":hidden").length > 0) {
                            count++;
                        }
                    }
                    return count;
                }

                // --- Initial attempt ---
                processCards('Initial');
                let cardsSuccessfullyHiddenSoFar = countCurrentlyHiddenCards();
                console.log("Initially hidden card count:", cardsSuccessfullyHiddenSoFar);


                if (cardsSuccessfullyHiddenSoFar < totalCardsToHide) {
                    console.log("Starting interval check as not all cards were hidden initially.");
                    let intervalAttempts = 0;
                    const maxIntervalAttempts = 20; // Try for 10 seconds (20 * 500ms)
                    const intervalId = setInterval(function() {
                        intervalAttempts++;
                        console.log(`  [Interval ${intervalAttempts}] Checking cards...`);

                        processCards(`Interval ${intervalAttempts}`);
                        cardsSuccessfullyHiddenSoFar = countCurrentlyHiddenCards();

                        console.log(`  [Interval ${intervalAttempts}] Total cards successfully hidden so far: ${cardsSuccessfullyHiddenSoFar}`);

                        if (cardsSuccessfullyHiddenSoFar >= totalCardsToHide || intervalAttempts >= maxIntervalAttempts) {
                            clearInterval(intervalId);
                            if (intervalAttempts >= maxIntervalAttempts && cardsSuccessfullyHiddenSoFar < totalCardsToHide) {
                                console.log(`Max interval attempts reached. ${totalCardsToHide - cardsSuccessfullyHiddenSoFar} card(s) might not have rendered or selectors are incorrect.`);
                                cardNamesToHide.forEach(cardName => {
                                    if ($(cardsToHideSelectors[cardName] + ":hidden").length === 0 && $(cardsToHideSelectors[cardName]).length > 0) {
                                        console.warn(`  - Card '${cardName}' was found but is NOT hidden.`);
                                    } else if ($(cardsToHideSelectors[cardName]).length === 0) {
                                        console.warn(`  - Card '${cardName}' was NOT found.`);
                                    }
                                });
                            } else {
                                console.log("All expected cards hidden via interval check, or max attempts reached.");
                            }
                        }
                    }, 500);
                } else {
                    console.log("All expected cards hidden on initial try. No interval needed.");
                }

            } else {
                console.log(`User is NOT (Instructor AND NOT System Manager). ${totalCardsToHide} cards will be visible.`);
                // Ensure cards are visible
                for (const cardName of cardNamesToHide) {
                    $(cardsToHideSelectors[cardName]).css('display', ''); // or .show()
                }
                console.log("All targeted cards ensured to be visible for this user type.");
            }
        } else {
            console.error("Error: frappe or frappe.user_roles is not available!");
        }
    }
});